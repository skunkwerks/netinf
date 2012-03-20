#
# NI Routing Table configuration
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

require 'routedsl'

# Examples for routing table entry specification using the DSL
# specified in 'routedsl.rb'

# sytnax:
# route add <regex>, <destination-uri>, <options>
# route add <string>, <destination-uri>, <options>
# route del <regex>, <destination-uri>

route add /^ni\:\/\/village\.n4c\.eu\/.*/, 'nihttp://village.n4c.eu', {:prio=>10}

route add 'ni://village.n4c.eu/sha-256;pbJzzNm2CZyRD5NhgXgiFPkT3G_O4NYOg5f1IFMg1Ag', 'nihttp://village.n4c.eu', {:prio=>1, :redirect=>true}


route add /^ni\:\/\/ietf\.org\/.*/, 'nihttp://village.n4c.eu', {:prio=>1, :nocache=>true, :redirect=>true}

route add /^ni\:\/\/ietf.*/, 'nihttp://village.n4c.com', {:prio=>255, :nocache=>true}

#route del 'ni://ietf.org/.*', 'nihttp://village.n4c.eu'
