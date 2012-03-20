#
# NI mount table implementation in Ruby
#
# This is the NI URI library developed as
# part of the SAIL project. (http://sail-project.eu)
#
# Specification(s) - note, versions may change::
# * http://tools.ietf.org/html/farrell-decade-ni-00
# * http://tools.ietf.org/html/draft-hallambaker-decade-ni-params-00
#
# Author:: Dirk Kutscher <kutscher@neclab.eu>
# Copyright:: Copyright (c) 2012 Dirk Kutscher <kutscher@neclab.eu>
# Specification:: http://tools.ietf.org/html/draft-farrell-decade-ni-00
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
#


require 'singleton'
require 'ni'

# The mount table for storing mappings from NI names to other
# URIs -- a Singleton. The mappings can be a transformation specification.
# See map.rb for examples.

class MountTab
  include Singleton
  
  def initialize()
    @mtab=[]
  end

# add a mapping (transformation specifcation) to the table.
  def add(mountString)
    @mtab << mountString
  end

# get list of transformed URIs for NI URI (without checking)
# the whole table is traversed.
# return a list of result URIs (not all of them may be usable).
  def getRes(ni)                
    print "getRes: #{ni}\n"
    @mtab.map {|spec|
      u=ni.transform(spec)
      print "u=#{u}\n"
      if u && u.size>0
        uu=URI::parse(u)
      else
        uu=nil
      end
      print "uu=#{u}\n"
      uu
    }
  end
end

