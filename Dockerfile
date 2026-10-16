FROM python:3.14

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DEFAULT_TIMEOUT=100 \
    DOCKER=true \
    GIT_PYTHON_REFRESH=quiet

RUN apt-get update && apt-get install --no-install-recommends -y \
    build-essential \
    curl \
    ffmpeg \
    gcc \
    git \
    libavcodec-dev \
    libavdevice-dev \
    libavformat-dev \
    libavutil-dev \
    libcairo2 \
    libmagic1 \
    libswscale-dev \
    openssh-server \
    xfonts-75dpi \
    xfonts-base \
    && curl -fsSL https://deb.nodesource.com/setup_18.x | bash - \
    && apt-get install --no-install-recommends -y nodejs \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

WORKDIR /opt/HerokuSafe
COPY . .

RUN pip install --no-cache-dir --no-warn-script-location --disable-pip-version-check --upgrade -r requirements.txt

# Application code belongs to the image; the volume contains private data only.
CMD ["python", "-m", "heroku", "--root", "--no-git", "--data-root", "/data"]
