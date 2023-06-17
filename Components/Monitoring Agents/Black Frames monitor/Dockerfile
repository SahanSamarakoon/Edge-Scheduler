FROM python:3.9-bullseye

RUN apt-get update && apt-get install -y --no-install-recommends libatlas-base-dev ffmpeg libsm6 libxext6 gcc python3-opencv

RUN  apt-get clean && \
        rm -rf /var/lib/apt/lists/*

# Set the working directory
WORKDIR /app

# Copy your Python file into the container
COPY . .

# Upgrade pip and install the required Python packages
RUN python -m pip install pip --upgrade && pip install --index-url=https://www.piwheels.org/simple -r requirements.txt

CMD ["python3","./blackframes_monitor.py"]
