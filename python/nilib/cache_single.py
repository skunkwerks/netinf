#!/usr/bin/python
"""
@package nilib
@file cache_single.py
@brief Cache module for lightweight dedicated NI NetInf HTTP convergence layer
@brief (CL) server and NRS server.
@version $Revision: 1.01 $ $Author: elwynd $
@version Copyright (C) 2012 Trinity College Dublin and Folly Consulting Ltd
      This is an adjunct to the NI URI library developed as
      part of the SAIL project. (http://sail-project.eu)

      Specification(s) - note, versions may change
          - http://tools.ietf.org/html/draft-farrell-decade-ni-10
          - http://tools.ietf.org/html/draft-hallambaker-decade-ni-params-03
          - http://tools.ietf.org/html/draft-kutscher-icnrg-netinf-proto-00

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at
   
       - http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.

================================================================================

@details
Cache manager for NetInf node infrastructure.

This version of the cache is intended for use with multi-threaded single process
servers.  The cache is maintained in filesystem files.  Integrity is maintained
bya threading Lock object.  

The NetInf server manages a local cache of published information, NetInf NDOs.
In the storage_root directory there are two parallel sub-directories: an ni_ndo
and an ni_meta sub-directory where the content and affiliated data of the
content, respectively, are stored. In this package, the file storing the
affiliated data is called the 'metadata file'. See the
draft-kutscher-icnrg-netinf_proto specification for the relationship between
the terms 'affiliated data' and 'metadata': broadly, the affiliated data
represents all the extra attributes that need to be maintained in
association with the NDO.

In each sub-directory there is a sub-directory for each digest algorithm.
Each of these directories contains the file names are the digest of the
content (i.e., the digest in the ni: or nih: name).  These directories are
set up by niserver_main.py when the server is first started based on the
list of available digest algorithms supplied by the ni.py library.

For a given entry (i.e., unique digest) it is required that there
will be at least a metadata file.  The corresponding content may or may not
be present depending on whether it was published (or whether the server
decides to delete the file because of policy constraints - such as space
limits or DoS avoidance by deleting files after a certain length of time -
note that these are not currently implemented but may be in future).

To improve performance an in-memory cache is maintained of recently accessed
items.
================================================================================
@code
Revision History
================
Version   Date       Author         Notes
1.3       10/02/2013 Elwyn Davies   Added get_temp_path for use by gateway. 
1.2       14/12/2012 Elwyn Davies   Corrected error return from check_cache_dirs. 
1.1       05/12/2012 Elwyn Davies   Improved comments. Factored out exception
                                    definitions. Renamed to SingleNetInfCache.
1.0       04/12/2012 Elwyn Davies   Provide separate dictionary and shared
                                    memory versions for cache_list.
                                    Sorted out cache_put so that it is thread
                                    safe and deals with both new and update
                                    operations wwith one interface.
0.0       29/10/2012 Elwyn Davies   Factored out of nilib.
                                    Intended for use with Twisted
@endcode
"""

import os
import sys
import time
import json
import mmap
import posix_ipc as pipc
import tempfile
import threading

#=== Local package modules ===

from ni import NIname, UnvalidatedNIname, EmptyParams
from metadata import NetInfMetaData

#==============================================================================#
__all__ = ['SingleNetInfCache']

#==============================================================================#
#=== Exceptions ===
#------------------------------------------------------------------------------#
from ni_exception import InconsistentParams, InvalidMetaData, \
                         CacheEntryExists, NoCacheEntry

#==============================================================================#
class SingleNetInfCache:
    """
    @brief Manage the filing system cache of NetInf NDOs.

    @detail
    The cache only stores items using ni names (nih names will be converted
    to their nih equivalents before placing in the cache).
    
    The operations on the cache ae designed so that the actual cache updates
    can take place very quickly:
    - Metadata files are not expected to be large and the contents are written
      in one go.
    - Content files are created by renaming an existing file.  A place for
      creating temporary files in the storage root is provided so that
      renaming is guaranteed not to involve file copying.

    Metadata files contain a string encoded JSON object.  When this is loaded
    into memory, it is managed as a Python dictionary (to which it bears an
    uncanny resemblance!).  This is encapsulated in an instance of the
    NetInfMetaData class.

    To optmize access to the cache a small in-memory sub-cache is maintained
    using a LRU algorithm. This is indexed by the digest of the item and is
    implemented as a dictionary.  Each entry in the sub-cache is itself a
    dictionary with the following fields:
    hash_alg       name of hash_alg used for digest
    metadata       NetInfMetaData class instance or None
    content_path   pathname for content file
    content_exists flag indicating if content file is present
    last_access    date/time of last access as time in seconds since the epoch as
                   returned by time.time()
    """
    #==========================================================================#
    # CLASS CONSTANTS

    ##@var NDO_DIR
    # Pathname component identifying sub-directory under storage base for
    # content files
    NDO_DIR        = "/ndo_dir/"

    ##@var META_DIR
    # Pathname component identifying sub-directory under storage base for
    # metadata files
    META_DIR       = "/meta_dir/"

    ##@var TEMP_DIR
    # Pathname component identifying sub-directory under storage base for
    # temporary files
    TEMP_DIR       = "/.cache_temp/"

    ##@var MAX_MEMCACHE
    # Maximu number of entries to maintain in in-memory sub-cache
    MAX_MEMCACHE   = 20

    #==========================================================================#
    # INSTANCE VARIABLES
    ##@var temp_path
    # string - full pathname of temporaries directories

    ##@var logger
    # logging object instance - where to do logging

    ##@var loginfo
    # callable Convenience function for logging informational messages 

    ##@var logdebug
    # callable Convenience function for logging debugging messages 

    ##@var logwarn
    # callable Convenience function for logging warning messages 

    ##@var logerror
    # callable Convenience function for logging error messages

    ##@var memcache
    # dictionary containing in memory sub-cache

    #==========================================================================#
    #=== Constructor ===
    #==========================================================================#
    def __init__(self, storage_root, logger):
        """
        @brief Record storage root, set up logging functions and check cache
               structure

        @param storage_root string pathname for directory at root of cache tree
        @param logger object instance of logger object.
        """

        self.storage_root = storage_root

        # Setup logging functions
        self.logger   = logger
        self.loginfo  = logger.info
        self.logdebug = logger.debug
        self.logwarn  = logger.warn
        self.logerror = logger.error

        try:
            self.temp_path = self.check_cache_dirs()
        except IOError, e:
            self.logerror("Cache directory tree not accessible: %s" % str(e))
            raise IOError("Cache directory tree not accessible")

        # Set up empty in memory cache
        self.memcache = {}

        # Lock for cache access
        self.cache_lock = threading.Lock()

        # Set temporary directory to be used for creating temporary dirs
        tempfile.tempdir = self.temp_path

        return

    #==========================================================================#
    #=== Private methods ===
    #==========================================================================#
    def _content_pathname(self, hash_alg, digest):
        """
        @brief Construct pathname for content file for given hash_alg and digest
        @param hash_alg string hash algorithm name used for entry
        @param digest string urlencoded base64 ni scheme digest for entry
        @return content file path name
        """
        return "%s%s%s/%s" % (self.storage_root, self.NDO_DIR, hash_alg, digest)

    #--------------------------------------------------------------------------#
    def _metadata_pathname(self, hash_alg, digest):
        """
        @brief Construct pathname for metadata file for given hash_alg and digest
        @param hash_alg string hash algorithm name used for entry
        @param digest string urlencoded base64 ni scheme digest for entry
        @return metadat file path name
        """
        return "%s%s%s/%s" % (self.storage_root, self.META_DIR, hash_alg, digest)
    
    #--------------------------------------------------------------------------#
    def _make_sub_cache_entry(self, digest, hash_alg, metadata,
                              content_path, content_exists):
        """
        @brief Update eitsing entry or make new entry in sub-cache
        @param digest string key for entry - digest used to name content entries
        @param hash_alg string name of hash algorithm used for digest
        @param metadata object NetInfMetaData instance for cache entry
        @param content_path string path name for content file (may not exist
        @param content_exists boolean indicates if content_file present

        Delete oldest entry if already MAX_MEMCACHE entries and need new entry
        Build new dictionary and store in memcache for new entry
        Update metadata and content_exists flag for updates
        Record new last_accessed time.
        """
        if self._is_entry_in_sub_cache(digest):
            # Do update
            ue = self.memcache[digest]
            if metadata is not None:
                ue["metadata"]       = metadata
            if content_exists is not None:
                ue["content_exists"] = content_exists
            ue["last_accessed"]      = time.time()
            return
        
        #Otherwise make new entry
        while len(self.memcache.keys()) >= self.MAX_MEMCACHE:
            # Delete the entry with the oldest last_accessed field
            # .items() returns a list of (key, value) pairs
            # Apply sorted using "last_accessed" field in value (i[1])
            # Get first (i.e. oldest) entry in resulting sorted list
            # Use the key (i[0]) to delete the entry.
            del self.memcache[(sorted(self.memcache.items(),
                                      key = lambda i : i[1]["last_accessed"])[0])[0]]
        ne = {}
        ne["hash_alg"]       = hash_alg
        ne["metadata"]       = metadata
        ne["content_path"]   = content_path
        ne["content_exists"] = content_exists
        ne["last_accessed"]  = time.time()

        self.memcache[digest] = ne
        return

    #--------------------------------------------------------------------------#
    def _is_entry_in_sub_cache(self,digest):
        """
        @brief Check if entry for digest is in memory sub-cache
        @param digest string key for entry - digest used to name content entries
        @returns boolean indicating if there is an entry in the sub-cache
        """
        return digest in self.memcache
    
    #==========================================================================#
    #=== Public methods ===
    #==========================================================================#
    def get_temp_path(self):
        """
        @brief Return the directory used for temporary files in the cache
        @return string pathname for temporary file directory
        """
        return self.temp_path
    
    #--------------------------------------------------------------------------#
    def check_cache_dirs(self):
        """
        @brief Check existence of object cache directories and create if necessary
        @retval string pathname for temporaries directory
        @throwIOError if file operations go wrong

        The storage_root directory has to be created and writeable before
        starting the server.

        For the rest of the tree, directories will be created if they do not
        exist.

        The temporaries directory will also be be created if it does not exist
        and its pathname returned as the result of sucessfuloperations.

        Directories are checked to see they are readable, writeable and
        searchable if they exist.

        If an file IO operation fails, the appropriate exception is raised,
        logged and propagated. 
        """
        if not os.path.isdir(self.storage_root):
            self.logerror("Storage root directory %s does not exist." %
                          self.storage_root)
            raise IOError("Storage root directory does not exist")

        for tree_name in (self.NDO_DIR, self.META_DIR):
            tree_root = "%s%s" % (self.storage_root, tree_name)
            if not os.path.isdir(tree_root):
                self.loginfo("Creating object cache tree directory: %s" %
                             tree_root)
                try:
                    os.mkdir(tree_root, 0755)
                except Exception, e:
                    self.logerror("Unable to create tree directory %s : %s." % \
                                  (tree_root, str(e)))
                    raise
            for auth_name in NIname.get_all_algs():
                dir_name = "%s%s" % (tree_root, auth_name)
                if not os.path.isdir(dir_name):
                    self.loginfo("Creating object cache directory: %s" %
                                 dir_name)
                    try:
                        os.mkdir(dir_name, 0755)
                    except Exception, e:
                        self.logerror("Unable to create cache directory %s : %s." %
                                      (dir_name, str(e)))
                        raise
                elif not os.access(dir_name, os.R_OK | os.W_OK | os.X_OK):
                    self.logerror("Existing cache directory %s does not have rwx"
                                  "access permissions." % dir_name)
                    raise OSError("Cannot access cache directory")
                else:
                    self.logdebug("Existing cache directory %s has rwx permissions" %
                                  dir_name)

            temp_path = self.storage_root + self.TEMP_DIR
            if not os.path.isdir(temp_path):
                self.loginfo("Creating object cache temporaries directory: %s" %
                             temp_path)
                try:
                    os.mkdir(temp_path, 0755)
                except Exception, e:
                    self.logerror("Unable to create temporaries directory %s : %s." % \
                                  (temp_path, str(e)))
                    raise
            elif not os.access(temp_path, os.R_OK | os.W_OK | os.X_OK):
                self.logerror("Existing temporaries directory %s does not have rwx"
                              "access permissions." % temp_path)
                raise OSError("Cannot access cache directory")
            else:
                self.logdebug("Existing temporaries directory %s has rwx permissions" %
                              temp_path)
                # Clear out any files in temporary directory
                try:
                    rv = os.system("rm -rf %s/*" % temp_path)
                    if rv != 0:
                        self.logerror("rm operation on temporaries directory failed")
                        raise IOError
                except Exception, e:
                    self.logerror("Unable to empty temporaries directory: %s" %
                                  str(e))
                    raise
        return temp_path

    #--------------------------------------------------------------------------#
    def cache_put(self, ni_name, metadata, content_file):
        """
        @brief Make a new entry in the cache or update an existing one using
               the ni digest (base64 encoded) from ni_name as key
        @param ni_name object NIname instance validated and with non-empty params
        @param metadata object NetInfMetaData instance matching ni_name
        @param content_file string pathname for content_file or None
        @return 4-tuple - (NetInfMetaData instance with metadata for ni_name,
                           Either the content file name or None if not stored,
                           boolean - True if this was a new entry
                           boolean - True if content_file was a duplicate)
        @throw UnvalidatedNIname if ni_name is not validated
        @throw EmptyParams if ni_name doesn't have a digest set
        @throw InconsistentParams if both metadata and content_file are None or
                                  ni field in metadata does not match ni_name url

        Assumes: For new cache entry - neither metadata of content file have
                 been written before 

        Check:
        - can get a canonical ni url out of ni_name
        - metadata is an instance of NetInfMetaData, and
        - that ni field in metadata matches canonical ni name
        - if content_file is not none, check it is a regular file
        Raise exception if fails

        Determine file names for metadata and content file

        Lock the cache

        Check if files exist:
        - Can't have content without metadata
        - If neither exists - record we are making new entry; otherwise update
        - For new entry:
          - If content (temporary) file supplied, rename as permanent content
          - Write metadata to file as JSON encoded string
        - For update entry:
          - If there is existing content file:
            - if content file supplied record that it was ignored
            - delete the temporary file
          - If there is no existing content file and content (temp) file supplied
            - rename the supplied file as the current content file
          - Read the metadata file into a NetInfMetaData instance
          - Merge the supplied metadata with the existing metadata
        - If content file now in place record that content exists

        Raise IOerror exception if any IO error occurs
        - If there is a failure while entering/updating metadata and
          a new content file was created, then remove it again.

        If all goes well, add new or update entry in sub-cache,
        release cache lock and return 5-tuple with
        - new/updated metadata
        - content file name or None
        - boolean indicating if was new entry
        - boolean indicating if supplied content file was ignored
        """
        if metadata is None:
            err_str = "put_cache: Must supply metadata for cache entry: %s" % \
                      ni_name.get_url()
            self.logerror(err_str)
            raise NoMetaDataSupplied(err_str)
        assert isinstance(metadata, NetInfMetaData)

        if (content_file is not None) and (not os.path.isfile(content_file)):
            err_str = "put_cache: Content file %s is not present: %s" % \
                      (content_file, ni_name.get_url())
            self.logerror(err_str)
            raise ValueError(err_str)
            
        try:
            ni_url = ni_name.get_canonical_ni_url()
            ni_hash_alg = ni_name.get_alg_name()
            ni_digest = ni_name.trans_nih_to_ni()
        except (UnvalidatedNIname, EmptyParams), e:
            err_str = "put_cache: bad ni_name supplied: %s" % str(e)
            self.logerror(err_str)
            raise sys.exc_info()[0](err_str)

        if metadata.get_ni() != ni_url:
            err_str = "put_cache: ni urls in ni_name and metadata do not match: %s vs %s" % \
                      (ni_url, metadata.get_ni())
            self.logerror(err_str)
            raise InconsistentParams(err_str)

        mfn = self._metadata_pathname(ni_hash_alg, ni_digest)
        cfn = self._content_pathname(ni_hash_alg, ni_digest)

        # Need to hold lock as this can be called from several threads
        with self.cache_lock:
            mf_exists = os.path.isfile(mfn)
            cf_exists = os.path.isfile(cfn)

            new_entry = not mf_exists
            content_added = False

            # We are ready to put new or updated cache entry
            ignore_duplicate = False
            if cf_exists:
                content_exists = True
                if content_file is not None:
                    ignore_duplicate = True
                    self.loginfo("put_cache: Duplicate content file ignored: %s" %
                                 ni_url)
                    try:
                        os.remove(content_file)
                    except Exception, e:
                        err_str = "put_cache: removal of temporary file %s failed: " % \
                                  content_file
                        self.logerror(err_str + str(e))
                        raise sys.exc_info()[0](err_str + str(e))
            elif content_file is not None:
                err_str = "put_cache: problem renaming content file from %s to %s: " % \
                          (content_file, cfn)
                try:
                    os.rename(content_file, cfn)
                except Exception, e:
                    self.logerror(err_str + str(e))
                    raise sys.exc_info()[0](err_str + str(e))
                content_exists = True
                content_added = True
            else:
                content_exists = False

            if mf_exists:
                err_str = "put_cache: problem reading metadata file %s: " % \
                          mfn
                try:
                    f = open(mfn, "r+b")
                    js = json.load(f)
                except Exception, e:
                    self.logerror(err_str + str(e))
                    f.close()
                    if content_added:
                        os.remove(cfn)
                    raise sys.exc_info()[0](err_str + str(e))
                old_metadata = NetInfMetaData()
                old_metadata.set_json_val(js)
                if not old_metadata.merge_latest_details(metadata):
                    err_str = "put_cache: Mismatched information in metadata update: %s" % \
                              ni_url
                    self.logerror(err_str)
                    if content_added:
                        os.remove(cfn)
                    raise ValueError(err_str)
                need_open = False
            else:
                # Need to open new file for writing
                need_open = True
                old_metadata = metadata
                
            err_str = "put_cache: problem writing metadata file %s: " % mfn
            try:
                if need_open:
                    f = open(mfn, "wb+")
                else:
                    # Empty existing file
                    f.seek(0, os.SEEK_SET)
                    f.truncate(0)

                json.dump(old_metadata.json_val(), f)
                f.close()
            except Exception, e:
                self.logerror(err_str + str(e))
                if content_added:
                    os.remove(cfn)
                raise sys.exc_info()[0](err_str + str(e))

            self._make_sub_cache_entry(ni_digest, ni_hash_alg, metadata,
                                       cfn, content_exists)
            # End of with self.cache_write_lock
        return (old_metadata, cfn if content_exists else None,
                new_entry, ignore_duplicate)

    #--------------------------------------------------------------------------#
    def cache_get(self, ni_name):
        """
        @brief Return information about a cached NDO based on the ni_name
        @param ni_name object NIname instance validated and with non-empty params
        @return 2-tuple - (NetInfMetaData instance with metadata for ni_name,
                           Either the content file name or None if not stored)
        @throw UnvalidatedNIname if ni_name is not validated
        @throw EmptyParams if ni_name doesn't have a digest set

        Get canonical uri, hash algorithm name and digest from ni_name.

        If digest is in memory sub-cache return values from there
        Otherwise, check if there is a metadata file:
        - if not, raise NoCacheEntry exception
        - if so, read metadata and put into NetInfMetaData object instance
        - check if there is a corresponding content file

        Make a new sub-cache entry with the objects retrieved

        Return the metadata and the content file name if the file exists
        Note that this file will not currently be deleted as there is no
        unpublsih operation.  If there is an unpublish, it could be handled
        by opening a file descriptor for the content file and returning that
        as well.  The file would remain accessible via the file descriptor
        even if the directory entry is removed.
        """
        
        assert isinstance(ni_name, NIname)

        try:
            ni_url = ni_name.get_canonical_ni_url()
            ni_hash_alg = ni_name.get_alg_name()
            ni_digest = ni_name.get_digest()
        except (UnvalidatedNIname, EmptyParams), e:
            err_str = "%s: bad ni_name supplied: %s" % ("cache_get", str(e))
            self.logerror(err_str)
            raise sys.exc_info()[0](err_str)
        
        if self._is_entry_in_sub_cache(ni_digest):
            sce = self.memcache[ni_digest]
            sce["last_accessed"] = time.time()
            return (sce["metadata"],
                    sce["content_path"] if sce["content_exists"] else None)

        # Need to hold lock as this can be called from several threads
        with self.cache_lock:
            # Check if metadata file exists
            mfn = self._metadata_pathname(ni_hash_alg, ni_digest)
            if not os.path.isfile(mfn):
                raise NoCacheEntry("cache_get: no metadata file for %s" % ni_url)
            try:
                f = open(mfn, "rb")
                js = json.load(f)
                f.close()
            except Exception, e:
                err_str = "cache_get: Failed to read JSON string for metadata file %s: %s" % \
                          (mfn, str(e))
                self.logerror(err_str)
                raise Exception(err_str)

            metadata = NetInfMetaData()
            if not metadata.set_json_val(js):
                err_str = "cache_get: Invalid metadata read from %s" % mfn
                self.logerror(err_str)
                raise InvalidMetaData(err_str)

            # Check is content file exists
            cfn = self._content_pathname(ni_hash_alg, ni_digest)
            content_exists = os.path.isfile(cfn)

            # Write a sub-cache entry for what was just retrieved
            self._make_sub_cache_entry(ni_digest, ni_hash_alg, metadata,
                                       cfn, content_exists)

        return (metadata, cfn if content_exists else None)
        
    #--------------------------------------------------------------------------#
    def cache_list(self, alg_list = None):
        """
        @brief Construct a dictionary listing current cache contents for
               specified digest algorithms 
        @param alg_list list of strings of digest algorithm names or None (= all)
        @return dictionary with listing or None

        Check if alg_list contains valid names - or get all from NIname.
        Return None if no valid names

        Read the metadata directory entries for selected algorithm names
        Build a dictionary with an entry for each selected algorithm name
        Value for each is an array of objects with two entries:
        - "dgst": digest (ni format)
        - "ce":   boolean indicating if content file exists

        Return dictionary constructed if alg_list contains known algorithms
        Return None if anything goes wrong and log infomational message.

        Note that we don't use the lock here.  At present cache entries are
        never explicitly deleted so the worst that can happen is that the
        listing is shy of a (very) few last microsedond entries
        """
        all_algs = NIname.get_all_algs()
        if alg_list is None:
            alg_list = all_algs
        else:
            for alg in alg_list:
                if not alg in all_algs:
                    self.loginfo("cache_list: Unknown algorithm name requested %s" %
                                 alg)
                    return None
        rslt = {}
        for alg in alg_list:
            mfd = "%s%s%s" % (self.storage_root, self.META_DIR, alg)
            cfd = "%s%s%s" % (self.storage_root, self.NDO_DIR, alg)
            entries = []

            # All cache entries are required to have metadata file,
            # and may have content file
            try:
                for dgst in os.listdir(mfd):
                    ce = os.path.isfile("%s/%s" % (cfd, dgst))
                    entries.append( { "dgst": dgst, "ce": ce })
            except Exception, e:
                self.logerror("cache_list: error while listing for alg %s: %s" %
                              (alg, str(e)))
                return None
            rslt[alg] = entries

        return rslt
        
    #--------------------------------------------------------------------------#
    def cache_list_mem(self, alg_list = None):
        """
        @brief Construct a JSON encoded structure listing current cache contents
               and save it in a shared memory block.
        @param alg_list list of strings of digest algorithm names or None (= all)
        @return string name of pozix_ipc shared memory segment with data or None

        Check if alg_list contains valid names - or get all from NIname.
        Return None if no valid names

        Read the metadata directory entries for selected algorithm names
        Build a JSON object with an entry for each selected algorithm name
        Value for each is an array of objects with two entries:
        - "dgst": digest (ni format)
        - "ce":   boolean indicating if content file exists

        JSON encode and place in a posix_ipc shared memory block
        Return name of memory block if all goes well
        Return None if anything goes wrong and log infomational message.
        """
        # Create a dictionary with the information
        list_dict = self.cache_list(alg_list)
        if list_dict is None:
            return None
        
        # JSON encode results
        js = json.dumps(list_dict)
        try:
            blk = pipc.SharedMemory(None, flags=pipc.O_CREX,
                                    mode=0600, size=len(js))
            f = mmap.mmap(blk.fd, blk.size)
            f.write(js)
            f.close
            blk.close_fd()
        except Exception, e:
            self.logerror("cache_list: Problem while writing to shared memory block: %s" %
                          str(e))
            return None

        # Ought to clean this block up periodically -
        # will go when process ends for now
        return blk.name
        
    #--------------------------------------------------------------------------#
    def cache_mktemp(self):
        """
        @brief Create a temporary file using tempfile.mkstemp
        @returns 2-tuple result of mkstemp: (open fd, path name)

        The temporary file is created in the .cache_temp subdirectory of the
        storage root so that it is guaranteed that it can be renamed into
        a content file under the storage root without having to copy files
        because it is on the same file system (and hence can use 'rename'.
        """
        return tempfile.mkstemp()
    
#==============================================================================#
if __name__ == "__main__":
    import sys
    import logging
    logger = logging.getLogger("test")
    logger.setLevel(logging.DEBUG)
    ch = logging.StreamHandler()
    fmt = logging.Formatter("%(levelname)s %(threadName)s %(message)s")
    ch.setFormatter(fmt)
    logger.addHandler(ch)
    storage_root = "/tmp/test"

    if os.path.exists(storage_root):
        if os.path.isfile(storage_root):
            try:
                os.remove(storage_root)
            except Exception, e:
                logger.error("Cannot remove test storage root %s file: %s" %
                             (storage_root, str(e)))
                sys.exit(1)
        else:
            try:
                os.system("rm -rf %s" % storage_root)
            except Exception, e:
                logger.error("Cannot remove test storage root %s dir: %s" %
                             (storage_root, str(e)))
                sys.exit(1)

    try:
        os.mkdir(storage_root)
    except Exception, e:
        logger.error("Cannot create test storage root %s dir: %s" %
                     (storage_root, str(e)))
        sys.exit(1)
        
    cache_inst = SingleNetInfCache(storage_root, logger)
    f = open(cache_inst.temp_path+"temp", "w")
    f.write("some_text")
    f.close()
    cache_inst2 = SingleNetInfCache(storage_root, logger)
    if os.path.isfile(cache_inst2.temp_path+"temp"):
        print"Temporaries not cleared"
        
    #---------------------------------------------------------------------------#
    ni_url = "ni://mumble.org/sha-256-32;uzFqGA"
    ni_name = NIname(ni_url)
    ni_name.validate_ni_url(has_params=True)
    ni_name_uv = NIname(ni_url)
    ni_name_np = NIname("ni:///sha-256")
    ni_name_np.validate_ni_url(has_params=False)
    print(str(ni_name.get_url()))
    md = NetInfMetaData(ni_name.get_canonical_ni_url(), "now",
                        loc1="http://www.example.com",
                        extrameta={ "something" : "else" })
    print(md)
    md1 = NetInfMetaData("ni://abr.org/sha_256_64;fjhaie8978", "now",
                         loc2="https://zzz.mumble.org",
                         extrameta={ "something" : "else" })
    print md1
    
    try:
        m, f, n, i = cache_inst.cache_put(ni_name_uv, md, None)
        print "Fault: cache_put accepted unvalidated ni_name"
    except Exception, e:
        print "Error correctly detected: %s" % str(e)
    try:
        m, f, n, i = cache_inst.cache_put(ni_name_np, md, None)
        print "Fault: cache_put accepted ni_name with no digest"
    except Exception, e:
        print "Error correctly detected: %s" % str(e)
    try:
        m, f, n, i = cache_inst.cache_put(ni_name, None, None)
        print "Fault: cache_put accepted call with no metadata"
    except Exception, e:
        print "Error correctly detected: %s" % str(e)
    try:
        m, f, n, i = cache_inst.cache_put(ni_name, md, "mumble")
        print "Fault: cache_put shouldn't work for ni_name as not present"
    except Exception, e:
        print "Error correctly detected: %s" % str(e)

    # Create a temporary file
    ts = "The quick brown fox jumped over the lazy fog"
    (tfd, tfn1) = cache_inst.cache_mktemp()
    tf = os.fdopen(tfd, "w")
    tf.write(ts)
    tf.close()
    print ("temp file name 1: %s" % tfn1)
    (tfd, tfn2) = cache_inst.cache_mktemp()
    tf = os.fdopen(tfd, "w")
    tf.write(ts)
    tf.close()
    print ("temp file name 2: %s" % tfn2)

    try:
        m, f, n, i = cache_inst.cache_put(ni_name_uv, md, None)
        print "Fault: cache_put accepted unvalidated ni_name"
    except Exception, e:
        print "Error correctly detected: %s" % str(e)
    try:
        m, f, n, i = cache_inst.cache_put(ni_name_np, md, None)
        print "Fault: cache_put accepted ni_name with no digest"
    except Exception, e:
        print "Error correctly detected: %s" % str(e)
    try:
        m, f, n, i = cache_inst.cache_put(ni_name, md, None)
        print "cache_put: new entry successfully installed in cache: %s" % str(n)
        print cache_inst.memcache
    except Exception, e:
        print "Fault: valid cache_put caused exception"
    try:
        m, f, n, i = cache_inst.cache_put(ni_name, md1, None)
        print "Fault: updating with inconsistent metadata succeeeded"
    except Exception, e:
        print "Error correctly detected: %s" % str(e)
    try:
        m, f, n, i = cache_inst.cache_put(ni_name, md, None)
        print "cache_put correctly accepted duplicate metadata entry"
        print "Metadata: ", m
    except Exception, e:
        print "Fault: valid cache_put caused exception: %s" % str(e)

    md.add_new_details("later", None, "bollix.tcd.ie", None)
    try:
        m, f, n, i = cache_inst.cache_put(ni_name, md, None)
        print "cache_put: updated metadata successfully installed in cache"
        print "New: %s; Ignored: %s" % (n, i)
        print cache_inst.memcache
    except Exception, e:
        print "Fault: valid cache_put caused exception: %s" % str(e)
    try:
        md.set_size(len(ts))
        md.set_ctype("text/plain")
        m, f, n, i = cache_inst.cache_put(ni_name, md, tfn1)
        print "cache_put: added content file successfully installed in cache"
        print "Metadata: ", m
        print "Content file: ", f
        print "New: ", n, "Ignored: ", i
        print cache_inst.memcache
    except Exception, e:
        print "Fault: valid cache_put caused exception: %s" % str(e)
    try:
        m, f, n, i = cache_inst.cache_put(ni_name, md, tfn2)
        print "cache_put: duplicate content file successfully ignored by cache"
        print "Metadata: ", m
        print "Content file: ", f
        print "New: ", n, "Ignored: ", i
        print cache_inst.memcache
    except Exception, e:
        print "Fault: valid cache_update caused exception: %s" % str(e)

    ln = cache_inst.cache_list_mem(None)
    print( "posix_ipc 'file name': %s" % ln)

    p = pipc.SharedMemory(ln)
    
    f = mmap.mmap(p.fd, p.size)
    # Unfortunately old versions of mmap require a length argument to read
    # so you can't just give the (not so) file-like mmap object to json.load()
    b = f.read(p.size)
    j = json.loads(b)
    print json.dumps(j, sort_keys=True, indent=4)
    f.close()
    
    
    
    
    

    
   
    
