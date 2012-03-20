#
# DSL for NI routing table management
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


require 'routing'

# Add a route with the specified arguments to the routing table.
# Syntax:
# * route add <regex>, <destination-uri>, <options>
# * route del <regex>, <destination-uri>
# see 'routes' file for examples
def route(args)
  routes=Routes.instance
  (cmd, pattern, dest, opts)=args

  d=URI::parse(dest)

  case cmd                  # route [add|remove]
  when :add
    routes.add(pattern, d, opts)
  when :remove
    routes.remove(pattern, d)
  end
end

def add(pattern, dest, options)
  [:add, pattern, dest, options]
end

def del(pattern, dest)
  [:remove, pattern, dest, nil]
end



#route add /^ni\:\/\/ietf\.org\/.*/, 'nihttp://village.n4c.eu', {:prio=>1, :nocache=>true, :redirect=>true}
#route add /^ni\:\/\/ietf.*/, 'nihttp://village.n4c.com', {:prio=>255, :nocache=>true}
#route remove 'ni://ietf.org/.*', 'nihttp://village.n4c.eu', {:prio=>1, :nocache=>true}
