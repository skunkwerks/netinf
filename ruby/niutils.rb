#
# niutils -- some useful functions for NI object handling
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

require 'ni'


# create an NI URI for the specified file, authority, using the
# specified hash algorithm
# tries to guess the content types and sets the <tt>ct</tt> query paramter
def hashFromFile(file, auth, algo)
  u = URI::NI.buildFromFile(auth, file, nil, algo)
  type=`file --mime-type #{file}`.split[1]
  u.contentType!(type)
  u
end

# create an NI URI for the specified HTTP resource, authority, using the
# specified hash algorithm
def hashFromWeb(uri, auth, algo)
  URI::NI.buildFromHTTP(auth, URI(uri), nil, algo)
end
