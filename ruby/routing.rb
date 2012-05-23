#
# NI routing table implementation in Ruby
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

require 'singleton'
require 'uri'

# RouteEntry consists of destination and options

class RouteEntry
  @dest
  @options
  attr_accessor :dest, :options

  def initialize(d,o)
    @dest=d
    @options=o
  end
end

# The routing table -- a Singleton.  The routing table maps regular
# expressions for NI URIs to next hop destinations. See 'routes.rb'
# for examples how to use it.

class Routes
  include Singleton
  
  def initialize()
    @route={}
  end

# add a routing entry.
# * pattern:: regular expression
# * dest:: next hop destination
# * options:: options (priorities etc.)
  def add(pattern, dest, options)
    options[:prio]=255 unless options[:prio] # default
    @route[pattern]=RouteEntry.new(dest, options)
  end
  
  def remove(pattern, dest)
    @route.delete(pattern)
  end

# returns an ordered list of [dest, options] according to priority
  def find(name)                
    print("finding route for #{name}\n")
    res={}
    resList=[]
    @route.each_pair do |p,d|
      match=if p.class==String
              name==p
            elsif p.class==Regexp
              name=~p
            else
              print "Routes::find: got #{p.class}\n"
              false
            end
      if match
        prio=d.options[:prio]
        if res.include?(d.dest)
          if res[d.dest][:prio]>prio
            res[d.dest]=d.options
          end
        else
          res[d.dest]=d.options
        end
      end
    end
    resList=res.to_a.map {|r| RouteEntry.new(r[0], r[1])}                    # as array of RouteEntry
    resList.sort! {|a,b| a.options[:prio] <=> b.options[:prio]} # sort by prio
  end                           # find
  
end

# syntactic sugar (to be used by DSL) for manipulating the routing table
def route(args)
  routes=Routes.instance
  (cmd, pattern, dest, opts)=args

  d=URI::parse(dest)

  case cmd                  # route [add|remove]
  when :add
    routes.add(pattern, d, opts)
  when :remove
    routes.remove(pattern, d, opts)
  end
end

# add an entry to the routing table
def add(pattern, dest, options)
  [:add, pattern, dest, options]
end

# remove an entry from the routing table
def remove(pattern, dest, options)
  [:remove, pattern, dest, options]
end



