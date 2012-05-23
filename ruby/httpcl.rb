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
require 'ni'
require 'netinf'

# HTTP convergence layer for NetInf
# implements GET, PUBLISH (object or registration), SEARCH

class NetInfHTTP < NetInf


# send a GET request
# loc can specify a next hop (HTTP URI)
#
# The algorithm:
# If (know_next_NetInf_hop) {
#     send this to FQDN/.well-known/netinfproto
#     POST <next-hop>
#     POST-data: form-encoded NetInf GET message
#     URI=ni://...&msg-id=foo&ext=bar
# } else {
#     // order needs fixing here
#     if (ni has authority) {
#         POST to WKU
#         POSTDATA as before
#     } 
#     if (ni has locator hints) {
#         try those
#     }
#     else 404
# }

  def get(niUri, msgId, loc=nil) # for now: loc=FQDN
    
    httpuri= if loc
               URI::parse("http://#{loc}/.well-known/netinfproto/get")
             else
               URI::parse(niUri.to_wellknownURI)
             end

    # FIXME locator hints to be done later
    
    res=Net::HTTP.post_form(httpuri, 'URI'  => niUri.to_s, 'msgid' => msgId, 'ext' => "no extension")
  end


# publish the specified object (send it)
# loc can specify a next hop (HTTP URI)
  def publishObj(niUri, file, destHost, msgId)
#    print ("publish: #{niUri}, #{file}, #{destHost}, #{msgId}\n")
    url=URI::parse("http://#{destHost}/.well-known/netinfproto/publish")
    
    res=nil

    File.open(file) do |obj|
      req = Net::HTTP::Post::Multipart.new(url.path,
            "octets" => UploadIO.new(obj, "application/octet-stream", file),
                                          "URI" => niUri.to_s,
                                           "msgid" => msgId,
       #                          "loc1" => "",
       #                          "loc2" => "",
                                           "fullPut" => "yes")
      print "Sending #{req} to #{url}\n"
      res = Net::HTTP.start(url.host, url.port) do |http|
        http.request(req)
      end
    end 
    
    res
    
  end                           # publishObj

# publish the specified object (registering it's location)
# loc can specify a next hop (HTTP URI)
  def publishLoc(niUri, locList, destHost, msgId)
    url=URI::parse("http://#{destHost}/.well-known/netinfproto/publish")

    res=nil
    req=nil

    loc1=locList[0]
    loc2=locList[1]
    
    if loc2
      req = Net::HTTP::Post::Multipart.new(url.path,
                                           "URI" => niUri.to_s,
                                           "msgid" => msgId,
                                           "loc1" => loc1,
                                           "loc2" => loc2)
    elsif loc1
      req = Net::HTTP::Post::Multipart.new(url.path,
                                           "URI" => niUri.to_s,
                                           "msgid" => msgId,
                                           "loc1" => loc1)
    end
    if req
      print "Sending request: #{req.to_s} to #{url}\n"
      
      res = Net::HTTP.start(url.host, url.port) do |http|
        http.request(req)
      end 
    end
    res
    
  end                           # publish


# send a SEARCH request to the specified next hop
  def search(loc, msgId)

    httpuri=URI::parse("http://#{loc}/.well-known/netinfproto/search")
    Net::HTTP.post_form(httpuri, 'msgid' => msgId, 'ext' => "no extension")
  end
  
end
