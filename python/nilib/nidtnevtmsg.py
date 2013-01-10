#!/usr/bin/python
"""
@package nilib
@file nidtnevtmsg.py
@brief Class encapsulating messages sent betweenDTN threads and cache manager.
@version $Revision: 0.05 $ $Author: stephen $
@version Copyright (C) 2012 Trinity College Dublin and Folly Consulting Ltd
	  This is an adjunct to the NI URI library developed as
	  part of the SAIL project. (http://sail-project.eu)

	  Specification(s) - note, versions may change
		  - http://tools.ietf.org/html/draft-farrell-decade-ni-10
		  - http://tools.ietf.org/html/draft-hallambaker-decade-ni-params-03
		  - http://tools.ietf.org/html/draft-kutscher-icnrg-netinf-proto-00

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at
   
	   -http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
===============================================================================#

@detail
Class encapsulating messages sent betweenDTN threads and cache manager.

@code
Revision History
================
Version   Date	     Author	    Notes
1.0	  01/01/2013 ElwynDavies    Created.

@endcode
"""

#==============================================================================#
# Standard modules

import dtnapi

#==============================================================================#
class MsgDtnEvt:
    """
    @brief Queue message encapsulation for bundles
    """
    
    # Direction of message - or terminate receiving process
    MSG_FROM_DTN = "dtn_recv"
    MSG_TO_DTN = "dtn_send"
    MSG_END = "end_ops"

    #--------------------------------------------------------------------------#
    def __init__(self, send_type, bundle):

        # Check the parameters are valid
        # (note the file *might* change under our feet - no guarantees later)
        if send_type not in (self.MSG_FROM_DTN, self.MSG_TO_DTN, self.MSG_END):
            raise ValueError
        if not ((send_type == self.MSG_END) or
                ((bundle is not None) and isinstance(bundle, dtnapi.dtn_bundle))):
            raise ValueError
        self._send_type = send_type
        self._bundle = bundle

    #--------------------------------------------------------------------------#
    def is_last_msg(self):
        return self.send_type == MSG_END

    #--------------------------------------------------------------------------#
    def bundle(self):
        return self._bundle

    #--------------------------------------------------------------------------#
    def __repr__(self):
        if self._send_type == self.MSG_END:
            return "Ending operations."
        else:
            return "Bundle %s %s queued" % (self._bundle.__repr__,
                                            { self.MSG_FROM_DTN: "from DTN",
                                              self.MSG_TO_DTN: "to DTN"}[self._send_type])
        
#==============================================================================#
if __name__ == "__main__":
    b = dtnapi.dtn_bundle()
    evt = MsgDtnEvt(MsgDtnEvt.MSG_TO_DTN, b)
    print evt
    evt = MsgDtnEvt(MsgDtnEvt.MSG_FROM_DTN, b)
    print evt
    evt = MsgDtnEvt(MsgDtnEvt.MSG_END, None)
    print evt
