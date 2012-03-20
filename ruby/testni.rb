#
# units tests for NI URI format implementation in Ruby
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

$: << File.dirname(__FILE__)

require 'ni'
require 'httpcl'
require 'test/unit'
require 'base64'

class TestNI < Test::Unit::TestCase
  def test_parser
    print "Testing NI URI parser\n"

    u = URI::parse("ni://example.com/sha-256;LCa0a2j/xo/5m0U8HTBBNBNCLXBkg7+g+YpeiGJm564=?foo=bar&bla=fasel")
    assert_equal(u.scheme, 'ni')
    assert_equal(u.host, 'example.com')
    assert_equal(u.hashAlgo, :"sha-256")
    assert_equal(u.hash, Base64.decode64('LCa0a2j/xo/5m0U8HTBBNBNCLXBkg7+g+YpeiGJm564='))
    assert_equal(u.query, 'foo=bar&bla=fasel')
  end

  def test_serializer
    print "Testing NI URI serialization\n"
    u = URI::NI.new('ni', nil, 'www.example.com', nil, nil, "sha-256;erwd12345678", nil, nil, nil)
    
    assert_equal(u.to_s, "ni://www.example.com/sha-256;erwd12345678")
  end

  def test_hashing
    print "Testing NI URI hashing\n"
    u = URI::NI.new('ni', nil, 'www.example.com', nil, nil, "sha-256;erwd12345678", nil, nil, nil)
    u.setHash("Object content")
    assert(u.isValidName?("Object content"))
  end

  def test_hashing2
    print "Testin NI URI hashing of file object\n"
    u = URI::NI.buildFromFile("www.dirk-kutscher.info", "sail-logo.png")
    assert_equal("ni://www.dirk-kutscher.info/sha-256;fAZNDkwBcBj9QFYQjJ4JlRrT-L187TjznDrj9Ptj2zc", u.to_s) # FIXME: not verified
  end

  def test_hashing3
    print "Testin NI URI hashing of web object\n"
    u = URI::NI.buildFromHTTP("www.dirk-kutscher.info", URI("http://www.ietf.org/images/ietflogotrans.gif"))
    print u.to_s
    assert_equal("ni://www.dirk-kutscher.info/sha-256;Q-wXXNfdSCLYtt20jY794vELdCwABDazSZbYDbdB2fI?loc=http://www.ietf.org/images/ietflogotrans.gif", u.to_s) # FIXME: not verified
  end


  def test_hashing4
    print "Testing .wellknown URI generation\n"
    u = URI::parse("ni://example.com/sha-256;LCa0a2j/xo/5m0U8HTBBNBNCLXBkg7+g+YpeiGJm564=?foo=bar&bla=fasel")
    assert_equal(u.to_wellknownURI, 'http://example.com/.well-known/ni/sha-256/LCa0a2j_xo_5m0U8HTBBNBNCLXBkg7-g-YpeiGJm564?foo=bar&bla=fasel')
  end


  def test_hashing5
    print "Testing HTTP CL\n"

    ni="ni://village.n4c.eu/sha-256;LPmak-0TLnp28cBYL-FCf-4PUy2REBHxf8F6APm0Qcs"
    loc="village.n4c.eu"
    
    print "Trying to retrieve #{ni} from #{loc}...\n"

    msgId=Time.new.strftime("%Y%m%d%H%M%S")

    nhttp=NetInfHTTP.new
    obj=nhttp.get(URI::parse(ni), msgId, loc)
    print "returned object: #{obj}\n"
   
  end


  def test_hashing6
    print "Testing URI parsing and b64 encoding"

    ni="ni://village.n4c.eu/sha-256;LPmak-0TLnp28cBYL-FCf-4PUy2REBHxf8F6APm0Qcs"

    u = URI::parse(ni)
   
    assert_equal(u.to_s, ni)

  end
 end
