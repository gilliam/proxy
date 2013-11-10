# Copyright 2013 Johan Rydberg.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from gevent import monkey
monkey.patch_all()

import logging
from optparse import OptionParser
import os

from gevent import pywsgi 
from glock.clock import Clock
from gilliam.service_registry import ServiceRegistryClient

from .proxy import ProxyApp
from .resolver import ProxyResolver


def main():
    parser = OptionParser()
    parser.add_option("-p", "--port", dest="port", type=int,
                      help="listen port", metavar="PORT",
                      default=9001)
    parser.add_option('-D', '--debug', dest="debug",
                      default=False, action="store_true")
    (options, args) = parser.parse_args()

    # logging
    format = '%(levelname)-8s %(name)s: %(message)s'
    debug = os.getenv('DEBUG') or options.debug
    logging.basicConfig(
        level=logging.DEBUG if debug else logging.INFO,
        format=format)

    service_registry = ServiceRegistryClient(Clock())

    resolver = ProxyResolver(service_registry)
    logging.info("start serving requests on {0}.".format(options.port))
    pywsgi.WSGIServer(('', options.port), ProxyApp(resolver)).serve_forever()


if __name__ == '__main__':
    main()
