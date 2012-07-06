#
# units tests for NI URI format implementation in Ruby
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

$: << File.dirname(__FILE__)

require 'udpcl'
require 'test/unit'

class TestUDPCL < Test::Unit::TestCase
  def test_init
    print "Testing UDP CL init\n"
    a=NetInfUDP.new
    b=NetInfUDP.new

    a.mountProc(NetInfUDP::GET) do |request, response|
      print "a got GET request: #{request}\n"
      a.getResp(request.uri, request.msgId, ["loc1", "loc2"])

      response="a"
    end

    b.mountProc(NetInfUDP::GETRESP) do |request, response|
      print "b got GET-RESP request: #{request}\n"
      response="b"
    end

#    a.get("ni://abc", "123")
    b.get("ni://xyz", "456")
    sleep(2)

  end
end
