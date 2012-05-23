#
# NI mapping table implementation in Ruby
#
# This is the NI URI library developed as
# part of the SAIL project. (http://sail-project.eu)
#
# Specification(s) - note, versions may change::
# * http://tools.ietf.org/html/farrell-decade-ni
# * http://tools.ietf.org/html/draft-hallambaker-decade-ni-params
#
# Author:: Dirk Kutscher <kutscher@neclab.eu>
# Copyright:: Copyright (c) 2012 Dirk Kutscher <kutscher@neclab.eu>
#
# License:: http://www.apache.org/licenses/LICENSE-2.0.html
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


require 'singleton'
require 'uri'
require 'niutils'
require 'tabentry'

# Class for map entries
# using the Entry mixin from tabentry.rb

class MapEntry
  include Entry
end

# return the hash algorithm name specified in opts.
# default: sha-256
def getAlgo(opts)
  digestAlgo=opts[:hash-algo] if opts
  digestAlgo="sha-256" unless digestAlgo # there must be a better idiom for that...
end


# The mapping table -- a singleton.

class Mapping
  include Singleton
 
# create a new hash map 
  def initialize()
    @niMap=Hash.new
  end

# add a mapping for the specified URI
# accepted URI types are <tt>http</tt> and <tt>file</tt>
  def add(uri, auth, opts)
    u=URI::parse(uri)
    
    case u.scheme
    when "http"
      addHttp(u,auth,opts)  
    when "file"
      addFile(u.path, auth, opts)
    end
  end

# add a mapping for the specified file.
# will construct the NI name automatically
  def addFile(file,auth,opts)
    print ("addFile: #{file}\n")
    if File::exists?(file) && File::readable_real?(file)
      if File::directory?(file)
        addDir(file, auth, opts)
      else                      # is really a file
        digestAlgo=getAlgo(opts)
        ni=hashFromFile(File::realdirpath(file), auth, digestAlgo)
        # add this to our map now...
        print "Adding entry for #{ni.to_s}\n"
        @niMap.store(ni.to_s,MapEntry.new(URI("file://#{file}"),opts))
      end
    end
  end

# add mappings for files in the specified directory (recursively, if specified)
# will construct NI names automatically
  def addDir(dir, auth, opts)
    print "Adding directory #{dir}\n"
    Dir.foreach(dir) do |entry|
      if entry!="." && entry!='..'
        path=File::absolute_path(entry, dir)
        if File::directory?(entry) && opts && opts[:recurse]
          addDir(path, auth, opts)
        else
          addFile(path, auth, opts)
        end
      end
    end
  end
    
# add a mapping for the specified HTTP resource
# will construct the NI name automatically
  def addHttp(uri,auth,opts)
    digestAlgo=getAlgo(opts)
    ni=URI::NI.buildFromHTTP(auth, uri, nil, digestAlgo)
    print "add HttP: #{@niMap.class}, #{ni.class}: #{ni}\n"
    @niMap.store(ni.to_s,MapEntry.new(uri,opts))
  end


# lookup the NI name in the mapping table and return the entry if found
# return nil if not found
  def find(name) 
    @niMap[name.to_s]
  end                           # find
  
# return a list of all mapped NI URIs
  def allNames
    @niMap.keys
  end

end

