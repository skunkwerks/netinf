#
# utils -- some useful functions 
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

module Base16
      def self.decode(s)
      hexStringList=s.scan(/[0-9a-f]{2}/)
      hexlist=hexStringList.map {|hx| hx.to_i(base=16)}
      hexlist.pack("C*")
    end

    def self.encode(s)
      hexlist=s.unpack("C*")
      hexStringList=hexlist.map { |c| 
        t=c.to_s(base=16)
        if(t.length==1)
          "0" + t
          else
          t
        end
      }
      hexStringList.join
    end

    def self.luhn(s)
      factor=2
      sum=0
      n=16

      s.reverse!

      s.each_char {|c|
        codePoint=c.to_i(base=n)
        addend=factor*codePoint
        factor=(factor==2)?1:2
        addend=(addend / n) + (addend % n)
        sum+=addend }
      remainder=sum %n
      checkCodePoint=(n-remainder)%n
      checkCodePoint.to_s(base=n)
    end

end
