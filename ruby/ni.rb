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


require 'uri'
require 'base64'
require 'utils'
require 'digest'
require 'digest-trunc'
require 'net/http'

# Extending Ruby's URI classes

module URI

# common functions for NI and NIH URIs
  module NICOMMON
    @@HASH = {
      :"sha-256" => Digest::SHA256,
      :"sha-384" => Digest::SHA384,
      :"sha-512" => Digest::SHA512,
      :"sha-256-128" => DigestTruncated::SHA256_128,
      :"sha-256-120" => DigestTruncated::SHA256_120,
      :"sha-256-96" => DigestTruncated::SHA256_96,
      :"sha-256-64" => DigestTruncated::SHA256_64,
      :"sha-256-32" => DigestTruncated::SHA256_32}
    
    @@HASHSUITEID = {
      :"reserved" => 0,
      :"sha-256" => 1,
      :"sha-256-128" => 2,
      :"sha-256-120" => 3,
      :"sha-256-96" => 4,
      :"sha-256-64" => 5,
      :"sha-256-32" => 6,
      :"reserved2" => 32}
    
    @@HASHNAME = @@HASHSUITEID.invert

    # The hash algorithm of the NI URI
    attr_reader :hashAlgo


    # The hash value of the NI URI
    attr_accessor :hash


# setting the hash function
    def hashFunc!(hashAlgo) 
#      print ("hashAlgo: #{hashAlgo} (Class: #{hashAlgo.class})\n")
      hashAlgo=hashAlgo.to_s
      ha=hashAlgo.to_i
      if ha!=0
        @hashAlgo = @@HASHNAME[ha]
      else
        @hashAlgo = hashAlgo.to_sym
      end
      @hashFunc =
        if @@HASH[@hashAlgo]
          @@HASH[@hashAlgo].new      
        else
          nil
        end
    end


# calculate the hash for obj and update the member    
    def setHash(obj)
      @hash = @hashFunc.digest(obj)
    end

# returns true if the hash of obj matches this NI URI
    def isValidName?(obj)                  # check name-data integrity for obj
      @hash == @hashFunc.digest(obj)
    end


# returns string representation of hash algorithm
    def algo
      @hashAlgo.to_s
    end

# Base64 decoding (using URI encoding) of the hash
    def b64tohash(b64)
      Base64.decode64(b64.tr("-_", "+/")+"=");           # FIXME: check for correctness
    end
    


# return the Base64-encoded hash value
    def hashAsBase64
      b=Base64.encode64(@hash)
      b.tr_s!("+/", "-_")
      b.delete!('=')
      b.strip!
      b
    end

# return NI URI representation
    def to_ni
      URI::parse("ni:///#{@hashAlgo.to_s + ';' + hashAsBase64}")
    end

# transform to NIH URI
    def to_nih
      hexhash=Base16::encode(@hash)
      URI::parse("nih:" + @hashAlgo.to_s + ';' + hexhash + ';' + Base16::luhn(hexhash))
    end




  end # NICOMMON



# NI is implementing NI URI construction, parsing etc.

  class NI < Generic

    
    
    COMPONENT = [
      :scheme, :host, :path, :query
    ].freeze


    include NICOMMON

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
#      print "NI hash val: #{@hash}\n"
    end


# compares two NI URIs by comparing the hash values
    def ==(other)
      res=(@hashAlgo==other.hashAlgo) && (@hash==other.hash)
      #if(!res)
#         print ("algos: #{@hashAlgo}, #{other.hashAlgo}\n")
#         print ("hashes: #{Base16::encode(@hash)}, #{Base16::encode(other.hash)}\n")
      # end
      res
    end


# return o (string) or empty string (if o is nil)
    def getUnlessNil(o)
      if o
        o
      else
        ''
      end
    end


# return URL segment representation of NI URI
    def to_urlSegment
      @hashAlgo.to_s + ';' + hashAsBase64
    end


# return string representation of NI URI
    def to_s
#      tmp=@scheme + '://' + getUnlessNil(@host) + '/' + @hashAlgo.to_s + ';' + hashAsBase64 + queryPart
      @scheme + '://' + getUnlessNil(@host) + '/' + to_urlSegment + queryPart
    end

# constuct .well-known URI from NI URI and return it as string
    def to_wellknownURI         # return well-known URI as specified in draft-farrell-decade-ni
      transform '"http://#{@host}/.well-known/ni/#{hashAlgo.to_s}/#{hashAsBase64 + queryPart}"'
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

# create binary format
    def to_bin
      suiteID=@@HASHSUITEID[@hashAlgo] & 63 # nullify two most-sigificant bits
      niData=[suiteID, @hash]
      niData.pack("Ca*")
    end

# create NI from binary format
    def self.buildFromBin(nibits)
      niData=nibits.unpack("Ca*")
      suiteID=niData[0]
      h=niData[1]
      algo=@@HASHNAME[suiteID]

      uri=build2([nil, "", nil], algo)
      uri.hash=niData[1]
      uri
    end


  end                           # NI class

# Human Readable NI URIs
  class NIH < Generic

    @checkSumError
    
    COMPONENT = [
      :scheme, :host, :path, :query
    ].freeze


    include NICOMMON



# constructing (see URI::HTTP)
    def self.build(args)
      tmp = Util::make_components_hash(self, args)
      return super(tmp)
    end


# the actual constructor
    def initialize(*arg)

      super(*arg)

      @checkSumError=false
      fields=@opaque.split(";")
#      print fields
      algo=fields[0]
      hashString=fields[1].tr("-","")
      h=Base16::decode(hashString)
      check=fields[2]
      if check && (Base16::luhn(hashString)!=check)
        @checkSumError=true
        print "nih checksum error: expected '#{Base16::luhn(fields[1])}', got '#{check}'\n"
      end
#      print "NIH hash algo string: #{algo}\n"
      hashFunc!(algo)
#      print "NIH hash algo: #{@hashAlgo}\n"
#      print "NIH hash val: #{h}\n"
      @hash=h
    end

# compares two NI URIs by comparing the hash values
    def ==(other)
      (@hashAlgo==other.hashAlgo) and (@hash==other.hash)
    end

# interleaves alphnum string with delimiter (after every four characters)
    def withDelimiter(str, delim)
      str.split(/([[:alnum:]]{4})/).keep_if {|item| item.length()>0}.join(delim)
    end


# return string representation of NIH URI
    def to_s
      algo=@@HASHSUITEID[@hashAlgo]
      if algo>0 && algo <=6
        algoString=algo.to_s
        else
        algoString=@hashAlgo.to_s
      end
      hexhash=Base16::encode(@hash)
      #@scheme + ':' + algoString + ';' + withDelimiter(hexhash, '-') + ';' + Base16::luhn(hexhash)
      @scheme + ':' + algoString + ';' + hexhash + ';' + Base16::luhn(hexhash)
    end


  end

  @@schemes['NI'] = NI

  @@schemes['NIH'] = NIH




end # module URI

