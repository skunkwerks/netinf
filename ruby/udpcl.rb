#
# NetInfUDP -- a UDP convergence layer for NetInf
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

require 'socket'
require 'ipaddr'
require 'thread'
require 'ni'
require 'netinf'
require 'json'

# defines a reader method  that returns the specified fieldName
def field_reader(funcName, fieldName)
  define_method(funcName) do | |
    self[fieldName]
  end
end

# returns the name of a setter method (by adding '=' to the sym argument)
def mkSetter(sym)
  (sym.to_s + '=').to_sym
end

# returns the name of a method (by adding 'Key' to the sym argument)
def mkKey(funcName)
  (funcName.to_s + 'Key').to_sym
end

# defines a setter method with the specified funcName for the
# specified fieldName
def field_setter(funcName, fieldName)
  define_method(mkSetter(funcName)) do |value |
    self[fieldName]=value
  end
end

# defines a class (static) function with the specified funcName that
# returns the specified fieldName
def field_key(funcName, fieldName)
  define_singleton_method(mkKey(funcName)) do | |
    fieldName
  end
end

# defines static functions and getter/setter functions. If fieldName
# is nil, the fieldName is derived from funcName
def field_accessor(funcName, fieldName=nil)
  fieldName=funcName.to_s unless fieldName
  field_reader(funcName, fieldName)
  field_setter(funcName, fieldName)
  field_key(funcName, fieldName)
end


# UDP Convergence Layer.
# for transmitting/receiving JSON-encoded messages

class NetInfUDP < NetInf

  MCADDR="225.4.5.6"
  PORT=2345
  MAXMSGSIZE=2**16


# Message class with message fields
  class Message < Hash
   
    field_accessor :msgType, "message type"
    field_accessor :uri, "URI"
    field_accessor :msgId
    field_accessor :locators
    field_accessor :instance
    field_accessor :version

  end # class Message
  
  GET="GET"
  GETRESP="GET-RESP"
  @@instance=0
  @socket
  @listener
  @id
  

# constructor: set up socket, start listening thread
  def initialize
    @mountTab=Hash.new
    @@instance+=1
    @id=(Process::pid.to_s) << '-' << (@@instance.to_s)

    @socket=UDPSocket.new

    @socket.setsockopt(Socket::Option.bool(:INET, :SOCKET, :REUSEADDR, true))
    @socket.bind(Socket::INADDR_ANY, PORT)

    optval = IPAddr.new(MCADDR).hton +
      IPAddr.new(Socket::INADDR_ANY, Socket::AF_INET).hton
    @socket.setsockopt(Socket::IPPROTO_IP, Socket::IP_ADD_MEMBERSHIP, optval)    
    
    @listener = Thread.start do 
      while true do
        print "recvfrom...\n"
        input, source = @socket.recvfrom(MAXMSGSIZE)
        addr = "%s:%d" % [source[3], source[1]] 

        msg=(JSON.parse(input))

        req=NetInfUDP::Message.new
        req.merge!(msg)
        if req.instance==@id
        else # Received #{input} from #{addr}\n"
          proc=@mountTab[req.msgType]
          print "proc=#{proc}\n"
          if proc
            response=""
            proc.call(req,response)
          end
        end
      end
    end
  end #initialize


# mount a handler for a message  
  def mountProc(dir, proc=nil, &block)
    proc ||= block
    @mountTab[dir]=proc
  end
  


# send message (must already be encoded)
  def send(msg)
    @socket.send(msg,0,MCADDR,PORT)
  end

# transform Message object to JSON and send it
  def sendMsg(para)
    msg={"instance" => @id,
      Message.versionKey => "NetInfUDP/1.0"}.merge(para)
    send(msg.to_json)
  end

# send the specified request (GET|GETRESP)
  def sendReq(msgType, niUri, msgId, para, loc=nil)
    sendMsg({Message.msgTypeKey => msgType,
      Message.uriKey => niUri.to_s,
      Message.msgIdKey => msgId}.merge(para))
  end

# send a GET request for the specified NI URI
  def get(niUri, msgId, loc=nil)
    sendReq(GET, niUri, msgId, {})
  end

# send a GETRESP message (as a response to a previously received GET
# request).
# Can currently only be used to return a list of locators (locList).
  def getResp(niUri, msgId, locList, loc=nil)
    sendReq(GETRESP, niUri, msgId, {Message.locatorsKey => locList})
  end

# send a PUBLISH (object) message -- to be implemented  
  def publishObj(niUri, file, destHost, msgId)
  end                           # publishObj

# send a PUBLISH (registration) request -- to be implemented  
  def publishLoc(niUri, locList, destHost, msgId)
  end                           # publish

# send a SEARCH request -- to be implemented  
  def search(loc, msgId)
  end
  
end                             # NetInfUDP
