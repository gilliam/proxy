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

"""Simple HTTP proxy.  Based on bitbucket.org/dahlia/wsgi-proxy."""

import httplib
import logging
import urlparse
import socket
import gevent
import os
import time

# The set of hop-by-hop headers.  All header names all normalized to
# lowercase.
HOPPISH_HEADERS = frozenset([
    'connection', 'keep-alive', 'proxy-authenticate',
    'proxy-authorization', 'te', 'trailers', 'transfer-encoding',
    'upgrade', 'proxy-connection'
])


def is_hop_by_hop(header):
    """Returns C{True} if the given C{header} is hop by hop."""
    return header.lower() in HOPPISH_HEADERS


def capitalize_header(hdr):
    return '-'.join([p.capitalize() for p in hdr.split('-')])


def reconstruct_url(environ):
    """Reconstruct the remote url from the given WSGI ``environ`` dictionary.

    :param environ: the WSGI environment
    :type environ: :class:`collections.MutableMapping`
    :returns: the remote url to proxy
    :rtype: :class:`basestring`

    """
    # From WSGI spec, PEP 333
    url = environ.get('PATH_INFO', '')
    if not url.startswith(('http://', 'https://')):
        url = '%s://%s%s' % (
            environ['wsgi.url_scheme'],
            environ['HTTP_HOST'],
            url
        )
    # Fix ;arg=value in url
    if '%3B' in url:
        url, arg = url.split('%3B', 1)
        url = ';'.join([url, arg.replace('%3D', '=')])
    # Stick query string back in
    try:
        query_string = environ['QUERY_STRING']
    except KeyError:
        pass
    else:
        url += '?' + query_string
    environ['reconstructed_url'] = url
    return url


class ProxyApp(object):
    """WSGI application to handle requests that need to be proxied."""

    connection_class = httplib.HTTPConnection

    def __init__(self, resolver=None):
        if resolver is None:
            resolver = lambda netloc: netloc
        self.resolver = resolver

    def _handle_connect(self, environ, start_response):
        """HTTP tunneling."""
        netloc = self.resolver(environ['PATH_INFO'])
        try:
            hostname, port = netloc.split(':',1)
            port = int(port)
        except TypeError:
            raise
        except ValueError:
            raise

        sock = socket.socket()
        sock.connect((hostname, port))

        def _forward(dst, src):
            while True:
                data = src.recv(4096)
                if data:
                    dst.sendall(data)
                else:
                    break

        write = start_response('200 OK', [('Connection', 'close')])
        write('')

        from gevent.fileobject import FileObject, SocketAdapter

        input = SocketAdapter(os.dup(environ['wsgi.input'].rfile.fileno()),
                           'rb')
        gevent.spawn(_forward, sock, input)
        try:
            while True:
                data = sock.recv(4096)
                if data:
                    yield data
                else:
                    break
        finally:
            sock.close()

    def handler(self, environ, start_response):
        """Proxy for requests to the actual http server"""
        logger = logging.getLogger(__name__ + '.WSGIProxyApplication.handler')

        if environ['REQUEST_METHOD'] == 'CONNECT':
            for data in self._handle_connect(environ, start_response):
                yield data
            return

        url = urlparse.urlparse(reconstruct_url(environ))

        # Create connection object
        try:
            connection = self.connection_class(self.resolver(url.netloc))
            # Build path
            path = url.geturl().replace('%s://%s' % (url.scheme, url.netloc),
                                        '')
        except Exception, err:
            start_response('501 Gateway Error', [('Content-Type', 'text/html')])
            logger.exception('Could not Connect')
            yield '<H1>Could not connect</H1>'
            print err
            import traceback
            traceback.print_exc()
            return

        # Read in request body if it exists
        body = None
        try:
            length = int(environ['CONTENT_LENGTH'])
        except (KeyError, ValueError):
            pass
        else:
            body = environ['wsgi.input'].read(length)

        # Build headers
        logger.debug('environ = %r', environ)
        headers = dict(
            (key, value)
            for key, value in (
                # This is a hacky way of getting the header names right
                (key[5:].lower().replace('_', '-'), value)
                for key, value in environ.items()
                # Keys that start with HTTP_ are all headers
                if key.startswith('HTTP_')
            )
            if not is_hop_by_hop(key)
        )

        # Handler headers that aren't HTTP_ in environ
        try:
            headers['content-type'] = environ['CONTENT_TYPE']
        except KeyError:
            pass

        # Add our host if one isn't defined
        if 'host' not in headers:
            headers['host'] = environ['SERVER_NAME']

        # Make the remote request
        try:
            logger.debug('%s %s %r',
                         environ['REQUEST_METHOD'], path, headers)
            connection.request(environ['REQUEST_METHOD'], path,
                               body=body, headers=headers)
        except Exception as e:
            # We need extra exception handling in the case the server fails
            # in mid connection, it's an edge case but I've seen it
            start_response('501 Gateway Error', [('Content-Type', 'text/html')])
            logger.exception(e)
            yield '<H1>Could not connect</H1>'
            return

        response = connection.getresponse()

        hopped_headers = response.getheaders()
        headers = [(capitalize_header(key), value)
                   for key, value in hopped_headers
                   if not is_hop_by_hop(key)]

        start_response('{0.status} {0.reason}'.format(response), headers)
        while True:
            chunk = response.read(4096)
            if chunk:
                yield chunk
            else:
                break

    def __call__(self, environ, start_response):
        return self.handler(environ, start_response)
