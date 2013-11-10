FROM gilliam/base
MAINTAINER Johan Rydberg <johan.rydberg@gmail.com>
ADD . /build/app
RUN mkdir -p /app /cache
RUN /bin/bash /build/buildpacks/heroku-buildpack-python/bin/compile /build/app /cache && rm -Rf /cache && rm -Rf /app && mv /build/app /app
EXPOSE 80
ENTRYPOINT ["/build/execute"]
