#
# NI URI format implementation in Ruby
#
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


require 'digest'

# truncate the given string s to nrbits bits
# limtation: works on byte boundaries only...

def truncateHash(s,nrbits)
  s.slice(0, nrbits/8)
end

def createTruncDigest(base, len)
  classname=base.name.split("::").last + "_" +  len.to_s
  newclass=::Class.new(base) do

    def digest(obj)
      truncateHash(super(obj), self.class.class_variable_get("@@hashlen"))
    end
  end

  newclass.class_variable_set("@@hashlen",len)  

#  print ("Creating #{classname}\n")
  DigestTruncated.const_set(classname, newclass )
end


module DigestTruncated

# this works, but is not DRY enough:

  # SHA256_64 = ::Class.new(Digest::SHA256) do
  #   def digest(obj)
  #     truncateHash(super(obj), 64)
  #   end
  # end

  # SHA256_128 = ::Class.new(Digest::SHA256) do
  #   def digest(obj)
  #     truncateHash(super(obj), 128)
  #   end
  # end

  # SHA256_120 = ::Class.new(Digest::SHA256) do
  #   def digest(obj)
  #     truncateHash(super(obj), 120)
  #   end
  # end

  # SHA256_96 = ::Class.new(Digest::SHA256) do
  #   def digest(obj)
  #     truncateHash(super(obj), 96)
  #   end
  # end

  # SHA256_32 = ::Class.new(Digest::SHA256) do
  #   def digest(obj)
  #     truncateHash(super(obj), 32)
  #   end
  # end



# BETTER:
# this creates SHA256_128, SHA256_120 etc.

  [128, 120, 96, 64, 32].each { |s| createTruncDigest(Digest::SHA256, s)}
  
end

