#
# NetInfHTTP -- an HTTP convergence layer for NetInf
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

require 'net/http'
require 'net/http/post/multipart'
require 'json'

# minimal name resolution service client interface
# provides registering and requesting authority name to routing hints mappings

module NRS

# default NRS server

  @@server="http://village.n4c.eu/netinfproto/rr"

  
# register the routing hints list elements under the key
  def NRS.reg(key, hintlist)

    httpuri= URI::parse(@@server)
    hint1, hint2 = hintlist

    res=Net::HTTP.post_form(httpuri, 'stage' => 'zero', 'URI' =>
                            key, 'hint1' => hint1, 'hint2' => hint2)

    res.body
  end

# lookup routing hints for key, returns list of keys
  def NRS.lookup(key)
    httpuri= URI::parse(@@server)

    res=Net::HTTP.post_form(httpuri, 'stage' => 'one', 'URI' => key)

    res.body

  end


# lookup routing hints for key, returns list of keys
  def NRS.list
    print "#{@@server}\n"
    httpuri= URI::parse(@@server)

    res=Net::HTTP.post_form(httpuri, 'stage' => 'two')
    res.body

  end
end

