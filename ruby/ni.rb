#
# NI URI format implementation in Ruby
#
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


require 'uri'
require 'base64'
require 'digest'
require 'net/http'

# Extending Ruby's URI classes

module URI

# NI is implementing NI URI construction, parsing etc.

  class NI < Generic

    HASH = {
      :"sha-256" => Digest::SHA256,
      :"sha-384" => Digest::SHA384,
      :"sha-512" => Digest::SHA512}

    
    COMPONENT = [
      :scheme, :host, :path, :query
    ].freeze

    # The hash algorithm of the NI URI
    attr_reader :hashAlgo


    # The hash value of the NI URI
    attr_reader :hash


# setting the hash function to use
    def hashFunc!(hashAlgo)
      @log.info("hashFunc!(#{hashAlgo})")
      @hashAlgo = hashAlgo.to_sym
      @hashFunc =
        if HASH[@hashAlgo]
          HASH[@hashAlgo].new      
        else
          nil
        end
    end

# constructing (see URI::HTTP)
    def self.build(args)
      tmp = Util::make_components_hash(self, args)
      return super(tmp)
    end

# constructing (see URI::HTTP)
    def self.build2(args, hashAlgo)
      uri=build(args)
      uri.hashFunc!(hashAlgo)
      uri
    end

# Base64 decoding (using URI encoding) of the hash
    def b64tohash(b64)
      Base64.decode64(b64.tr("-_", "+/")+"=");           # FIXME: check for correctness
    end

# the actual constructor
    def initialize(*arg)

      super(*arg)
      # have to parse algorithm and hash here...

      @hashAlgo = nil
      @hash = nil

      if path
        hpath=path
        if hpath[0]=='/'            # starts with "/"
          hpath.slice!(0)          # remove it
        end

        h=hpath.split(';')         # split in array with algo and hash

        if(h.length==2)
          hashFunc!(h[0])
          @hash=b64tohash(h[1])           # FIXME: check for correctness
        end
      end
    end


# return the Base64-encoded hash value
    def hashAsBase64
      b=Base64.encode64(@hash)
      b.tr_s!("+/", "-_")
      b.delete!('=')
      b.strip!
      b
    end

# return o (string) or empty string (if o is nil)
    def getUnlessNil(o)
      if o
        o
      else
        ''
      end
    end

# return string representation of NI URI
    def to_s
      tmp=@scheme + '://' + getUnlessNil(@host) + '/' + @hashAlgo.to_s + ';' + hashAsBase64 + queryPart
    end

# constuct .well-known URI from NI URI and return it as string
    def to_wellknownURI         # return well-known URI as specified in draft-farrell-decade-ni
      transform '"http://#{@host}/.well-known/ni/#{hashAlgo.to_s}/#{hashAsBase64 + queryPart}"'
    end

    
# calculate the hash for obj and update the member    
    def setHash(obj)
      @hash = @hashFunc.digest(obj)
    end

# returns true if the hash of obj matches this NI URI
    def isValidName?(obj)                  # check name-data integrity for obj
      @hash == @hashFunc.digest(obj)
    end

# compares two NI URIs by comparing the hash values
    def ==(other)
      (@hashAlgo==other.hashAlgo) and (@hash==other.hash)
    end

# returns string representation of hash algorithm
    def algo
      @hashAlgo.to_s
    end

# add a query parameter to this NI URI
    def addQuery(q)
      if @query
        @query+="&"
        else
        @query=''
      end
      @query+=q
    end

# add the named parameter to the query part of this NI URI
    def addPara(key, val)
      addQuery("#{key}=#{val}")
    end

# add a content type parameter to this NI URI
    def contentType!(t)
      addPara('ct',t)
    end

# return the value for named URI parameter (or nil if it does not exist)
    def para(key)
      res=nil
      if @query
        paras=query.split('&').map {|p| p.split('=')}
        t=paras.find {|p| p[0]==key}
        if t
          res=t[1]
        end
      end
      res
    end
    
# return content type URI paramter
    def contentType
      para('ct')
    end

# return loc URI parameter
    def loc
      para('loc')
    end

# set loc URI parameter
    def loc!(l)
      addPara('loc',l)
    end

# returns the query part of this NI URI
    def queryPart
      if @query
        '?' + @query
      else
        ''
      end
    end


# build an NI URI from file using the passed parameter. autority may be an empty string          
    def self.buildFromFile(authority, filename, query=nil, hashAlgo=:"sha-256")
      uri=build2([authority, "", query], hashAlgo)
      uri.setHash(File.new(filename).read)
      uri
    end

# build an NI URI from web object using the passed parameter. autority may be an empty string          
    def self.buildFromHTTP(authority, httpUri, query=nil, hashAlgo=:"sha-256")
      uri=build2([authority, "", query], hashAlgo)
      uri.setHash(Net::HTTP.get(httpUri))
      uri.loc!(httpUri.to_s)
      uri
    end

# returns the request URI of this NI URI
    def request_uri
      r = path_query
      if r[0] != ?/
        r = '/' + r
      end
      r
    end

# transforms this URI by evaluating the given expression expr.
    def transform(expr)
      eval(expr,binding)
    end


  end                           # NI class

  @@schemes['NI'] = NI

end

