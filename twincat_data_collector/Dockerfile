FROM ghcr.io/astral-sh/uv:trixie-slim


# The installer requires curl (and certificates) to download the release archive
RUN apt-get update && apt-get install -y --no-install-recommends \
	curl \
	ca-certificates

# Use login information in the bhf.conf file to authenticate against deb*.beckhoff.com
# See https://manpages.debian.org/testing/apt/apt_auth.conf.5.en.html for more information
RUN --mount=type=secret,id=apt \
    curl --fail --netrc-file "/run/secrets/apt" \
    -o /usr/share/keyrings/bhf.asc \
    https://deb.beckhoff.com/repo.pub

# Replace default debian.org package sources.
# From here on, all packages will be loaded from deb*.beckhoff.com
RUN rm /etc/apt/sources.list.d/debian.sources
COPY ./apt-config/bhf.list ./apt-config/debian.sources.list /etc/apt/sources.list.d/

# Install TwinCAT runtime package
RUN --mount=type=secret,id=apt \
    apt-get -o "Dir::Etc::netrc=/run/secrets/apt" update \
    && apt-get -o "Dir::Etc::netrc=/run/secrets/apt" install --yes \
    libadscomm \
    supervisor \
    tc31-xar-um \
    cmake \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# As an example, copy basic TwinCAT runtime configurations files
ARG TC3_DIR=/etc/TwinCAT/3.1
#COPY TwinCAT/StaticRoutes.xml $TC3_DIR/Target/

WORKDIR /app
ADD ./app /app


RUN uv sync --directory /app --frozen --no-dev

RUN mkdir -p /var/log/supervisor
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf


CMD [ "/usr/bin/supervisord"]
