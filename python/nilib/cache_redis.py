#!/usr/bin/python
"""
@package nilib
@file cache_redis.py
@brief Cache module for Apache mod_wsgi NI NetInf HTTP convergence layer (CL)
@brief server and NRS server using Redis NoSQL server for metadata.
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

This version of the cache is intended for use with multi-threaded multi-process
servers.  The cache is maintained in a combination of Redis database records
for the metedata and filesystem files for the content. Integrity is maintained
primarily bythe transaction mechanisms of the Redis database and the use of
atomic renane operations for the content files. The cache manager is essentially
stateless apart from its knowledge of the logger and the storage_root which
are set up when the instance is initialized.  It is recommended that only
instance of this object is created per process.

The NetInf server manages a local cache of published information, NetInf NDOs.
The content of the NDOs is atored under the storage_root directory in the
ni_ndo sub-directoryand an ni_meta. The correspondingIn this package, the file storing the
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
================================================================================
@code
Revision History
================
Version   Date       Author         Notes
1.1       14/12/2012 Elwyn Davies   Corrected error return from check_cache_dirs. 
                                    Ensured that STORAGE_ROOT_KEY is recreated.
1.0       06/12/2012 Elwyn Davies   Created from cache_multi for Redis.

@endcode
"""

import os
import fcntl
import errno
import sys
import time
import json
import mmap
import posix_ipc as pipc
import tempfile
import threading
import redis

#=== Local package modules ===

from ni import NIname, UnvalidatedNIname, EmptyParams
from metadata import NetInfMetaData

__all__ = ['RedisNetInfCache']

#==============================================================================#
#=== Exceptions ===
#------------------------------------------------------------------------------#
from ni_exception import InconsistentParams, InvalidMetaData, \
                         CacheEntryExists, NoCacheEntry, InconsistentDatabase

#==============================================================================#
class RedisNetInfCache:
    """
    @brief Manage the combined Redis and filing system cache of NetInf NDOs.

    @detail
    The cache only stores items using ni names (nih names will be converted
    to their nih equivalents before placing in the cache).
    
    The operations on the cache ae designed so that the actual cache updates
    can take place very quickly:
    - Metadata records are not expected to be large and the contents are written
      in one go.
    - Content files are created by renaming an existing file.  A place for
      creating temporary files in the storage root is provided so that
      renaming is guaranteed not to involve file copying.

    Metadata records contain a string encoded JSON object.  When this is loaded
    into memory, it is managed as a Python dictionary (to which it bears an
    uncanny resemblance!).  This is encapsulated in an instance of the
    NetInfMetaData class.

    When the class is initialized, the cache directory tree is checked out.  If
    there is a problem an IOError exception is raised.  Otherwise the check
    retrns the temporary file directory to use which is fed to the tempfile
    module.
    """
    #==========================================================================#
    # CLASS CONSTANTS

    ##@var NDO_DIR
    # Pathname component identifying sub-directory under storage base for
    # content files
    NDO_DIR        = "/ndo_dir/"

    ##@var TEMP_DIR
    # Pathname component identifying sub-directory under storage base for
    # temporary files
    TEMP_DIR       = "/.cache_temp/"

    ##@var STORAGE_ROOT_KEY
    # string key used to store storage root for this server
    STORAGE_ROOT_KEY = "NISERVER_STORAGE_ROOT"

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

        # Redis connection to be used with the cache
        # Set by set_redis_conn later.
        self.redis_conn = None

        try:
            self.temp_path = self.check_cache_dirs()
        except Exception, e:
            self.logerror("Cache directory tree not accessible: %s" % str(e))
            raise IOError("Cache directory tree not accessible")

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
    def _metadata_key_name(self, hash_alg, digest):
        """
        @brief Construct key name for metadata record for given hash_alg and
               digest.
        @param hash_alg string hash algorithm name used for entry
        @param digest string urlencoded base64 ni scheme digest for entry
        @return metadata file path name
        """
        return "%s;%s" % (hash_alg, digest)
    
    #==========================================================================#
    #=== Public methods ===
    #==========================================================================#
    def set_storage_root_key(self):
    
        assert(self.redis_conn is not None)

        # Check that connection works and the storage root is recorded
        try:
            storage_root = self.redis_conn.get(self.STORAGE_ROOT_KEY)
            if storage_root is None:
                rslt = self.redis_conn.set(self.STORAGE_ROOT_KEY, self.storage_root)
                if rslt:
                    return True
                else:
                    self.logerror("Unable to set storage root key in Redis")
                    return False
            else:
                if storage_root == self.storage_root:
                    # OK - database and program agree on storgae_root
                    return True
                else:
                    self.logerror("Storage_root in environment does not match value in database: %s" %
                                  storage_root)
                    return False
        except Exception, e:
            self.logerror("Failed to access Redis database on setting up cache: %s" %
                          str(e))
            return False

    #--------------------------------------------------------------------------#
    def set_redis_conn(self, redis_conn):
        """
        @brief Record redis connection object to be used by the cache
        @param redis_conn object instance of StrictRedis object.
        @return boolean indicating if connection works and storage root
                is OK

        """
        # Record Redis connection
        self.redis_conn = redis_conn
        self.logdebug("Redis connection passed to cache instance")

        return self.set_storage_root_key()

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

        # There is only one tree for the content files - metadata is in Redis
        for tree_name in (self.NDO_DIR,):
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
        if self.redis_conn is not None:
            if self.set_storage_root_key():
               return temp_path
            else:
               raise IOError("Unable to set storage root key in Redsi database")

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

        Lock the cache.  This is done by using a threading lock to cater for
        multiple threads in one process and also putting an exclusive flock
        lock on the metadata file to be accessed so that access is serialized
        between processes as well.

        Check if metadata record and (if expected) content file exist:
        - Can't have content without metadata
        - If neither exists - record we are making new entry; otherwise update
        - For new entry:
          - If content (temporary) file supplied, rename as permanent content
          - Write metadata to record as JSON encoded string
          - Write indicator of content present to metadata record
        - For update entry:
          - If there is existing content file:
            - if content file supplied record that it was ignored
            - delete the temporary file
          - If there is no existing content file and content (temp) file supplied
            - rename the supplied file as the current content file
          - Read the metadata file into a NetInfMetaData instance
          - Merge the supplied metadata with the existing metadata and
        - If content file now in place record that content exists

        Raise IOError exception if any IO error occurs
        - If there is a failure while entering/updating metadata and
          a new content file was created, then remove it again.

        If all goes well, release cache lock and return 5-tuple with
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

        mfk = self._metadata_key_name(ni_hash_alg, ni_digest)
        cfn = self._content_pathname(ni_hash_alg, ni_digest)

        # Need to hold lock as this can be called from several threads
        with self.cache_lock:

            content_added = False
            ignore_duplicate = False
            while True:
                # I think this should be OK.. even with nested try blocks
                # The outer try block is to catch WatchError from the
                # redis_pipe.watch() but this doesn't arrive asynchronously
                # (or at least I hope it doesn't).  Rather it is generated
                # as a result of a subsequent Redis request.  As long as these
                # are not buried in inner try blocks all should be well
                # except that the outer except needs to reraise anything except
                # WatchError.
                with self.redis_conn.pipeline() as redis_pipe:
                    try:
                        # Setup to monitor the metadata key in case it changes
                        redis_pipe.watch(mfk)

                        # get keys for content_file and metatdata
                        metadata_str, cfs = redis_pipe.hmget(mfk, "metadata",
                                                             "content_file_exists")

                        if (metadata_str is None) and (cfs is not None):
                            # Error
                            err_str = "put_cache: Redis inconsistent - has no metatdata but cfs for : %s" % \
                                      ni_url
                            self.logerror(err_str)
                            raise InconsistentDatabase(err_str)
                            
                        # Check for consistency
                        cfs_bool = (cfs == "yes")
                        cf_exists = os.path.isfile(cfn)
                        # If we have to loop then consistency may alter
                        if (cf_exists != cfs_bool) and not content_added:
                            # error - inconsistent
                            err_str = "put_cache: Redis inconsistent with file for %s" % \
                                      ni_url
                            self.logerror(err_str)
                            raise InconsistentDatabase(err_str)

                        # We are ready to put new or updated cache entry
                        # On second and subsequent passes
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

                        err_str = "put_cache: problem decoding metadata record %s: " % \
                                  mfk
                        try:
                            if (metadata_str is None):
                                new_entry = True
                                # Don't need a real copy - reference will do
                                old_metadata = metadata
                            else:
                                new_entry = False
                                js = json.loads(metadata_str)
                        except Exception, e:
                            self.logerror(err_str + str(e))
                            if content_added:
                                os.remove(cfn)
                            raise sys.exc_info()[0](err_str + str(e))

                        if not new_entry:
                            old_metadata = NetInfMetaData()
                            old_metadata.set_json_val(js)
                            if not old_metadata.merge_latest_details(metadata):
                                err_str = "put_cache: Mismatched information in metadata update: %s" % \
                                          ni_url
                                self.logerror(err_str)
                                if content_added:
                                    os.remove(cfn)
                                raise ValueError(err_str)
                            
                        err_str = "put_cache: problem storing metadata record %s: " % mfk
                        try:
                            new_metadata_str = json.dumps(old_metadata.json_val())
                        except Exception, e:
                            self.logerror(err_str + str(e))
                            if content_added:
                                os.remove(cfn)
                            raise sys.exc_info()[0](err_str + str(e))

                        cfs = "yes" if content_exists else "no"

                        # Write back into Redis
                        val_dict = {}
                        val_dict["metadata"] = new_metadata_str
                        val_dict["content_file_exists"] = cfs
                        # Start a transaction
                        redis_pipe.multi()
                        # Push the data update
                        redis_pipe.hmset(mfk, val_dict)
                        # Add this name to the set of keys for hash alg
                        # Doesn't matter if it is there already
                        # The set only has one entry for this value.
                        redis_pipe.sadd(ni_hash_alg, mfk)
                        # Run the update - if the data has changed
                        # since the watch was started, this will trigger
                        # a WatchError exception.
                        redis_pipe.execute()

                        # Sucess - break out of loop
                        # End of with clause resets the watch automatically
                        break
                    
                    except redis.WatchError:
                        # Go round again as somebody else updated
                        # We have done what is needed with the content_file
                        # and shouldn't try again.  The content is now
                        # in its cache home.
                        content_file = None

                        continue
                    
                    except Exception:
                        # This has caught one of the reraised exceptions
                        # buried in the loop - just reraise again to
                        # propagate to caller
                        raise
                    # End of with redis.pipeline()
                # End of WatchError catching loop
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

        Check if there is a metadata file:
        - if not, raise NoCacheEntry exception
        - if so, get a shared flock lock on it so that no other process can
          get old of it and update the contents while we are reading it, then
          read metadata and put into NetInfMetaData object instance
        - check if there is a corresponding content file

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
        
        # Need to hold lock as this can be called from several threads
        with self.cache_lock:
            # Check if metadata record exists
            mfk = self._metadata_key_name(ni_hash_alg, ni_digest)
            metadata_str, cfe = self.redis_conn.hmget(mfk, "metadata",
                                                      "content_file_exists")
            if (metadata_str is None) and (cfe is None):
                raise NoCacheEntry("cache_get: no metadata file for %s" % ni_url)
            if (metadata_str is None) and (cfe is not None):
                err_str = "cache_get: Inconsistent database entry for %s" % ni_url
                self.logerror(err_str)
                raise InconsistentDatabase(err_str)
            try:
               js = json.loads(metadata_str)
            except Exception, e:
                err_str = "cache_get: Failed to decode JSON string for metadata record %s: %s" % \
                          (mfk, str(e))
                self.logerror(err_str)
                raise Exception(err_str)

            metadata = NetInfMetaData()
            if not metadata.set_json_val(js):
                err_str = "cache_get: Invalid metadata read from %s record" % mfk
                self.logerror(err_str)
                raise InvalidMetaData(err_str)

            # Check if content file exists
            cfe_bool = True if cfe == "yes" else False
            cfn = self._content_pathname(ni_hash_alg, ni_digest)
            
            content_exists = os.path.isfile(cfn)
            if cfe_bool != content_exists:
                err_str = "cache_get: Inconsistent data entry for content existence: %s" % \
                          ni_url
                self.logerror(err_str)
                raise InconsistentDatabase(err_str)

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
            cfd = "%s%s%s" % (self.storage_root, self.NDO_DIR, alg)
            entries = []
            pl = len(alg) + 1
            for i in self.redis_conn.smembers(alg):
                # All cache entries are required to have metadata record,
                # and may have content file
                dgst = i[pl:]
                ce = os.path.isfile("%s/%s" % (cfd, dgst))
                entries.append( { "dgst": dgst, "ce": ce })
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
    import redis
    redis_conn = redis.StrictRedis()
    cache_inst = RedisNetInfCache(storage_root, logger)
    cache_inst.set_redis_conn(redis_conn)
    f = open(cache_inst.temp_path+"temp", "w")
    f.write("some_text")
    f.close()
    cache_inst2 = RedisNetInfCache(storage_root, logger)
    cache_inst2.set_redis_conn(redis_conn)
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
        print "Metadata: ", m
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
        print "Metadata: ", m
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
    except Exception, e:
        print "Fault: valid cache_put caused exception: %s" % str(e)
    try:
        m, f, n, i = cache_inst.cache_put(ni_name, md, tfn2)
        print "cache_put: duplicate content file successfully ignored by cache"
        print "Metadata: ", m
        print "Content file: ", f
        print "New: ", n, "Ignored: ", i
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
    
    
    
    
    

    
   
    
