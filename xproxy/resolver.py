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


from gilliam.service_registry import Resolver as ServiceRegistryResolver


class ProxyResolver(object):
    """Class that resolves host names for the proxy."""

    def __init__(self, registry):
        self.resolver = ServiceRegistryResolver(registry)

    def __call__(self, netloc):
        try:
            host, port = netloc.split(':', 1)
        except ValueError:
            host, port = netloc, 80
        host, port = self.resolver.resolve_host_port(host, int(port))
        return '%s:%d' % (host, port)
