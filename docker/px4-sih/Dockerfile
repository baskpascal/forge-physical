# This image is built from source, never from a floating PX4 SITL runtime tag.
# The builder digest and PX4 commit are part of the COUP Alpha verification lock.
FROM px4io/px4-dev-simulation-focal@sha256:de5eba2c8c86b0ca852de59354de7f4d85599ae30587fa9f2905bc0c52b46dd7

ARG PX4_COMMIT=d6f12ad1c4f70ad3230afd7d86e971421e02fef4
WORKDIR /opt
RUN git clone --recursive --depth 1 --branch v1.17.0 https://github.com/PX4/PX4-Autopilot.git px4 \
    && cd px4 \
    && test "$(git rev-parse HEAD)" = "$PX4_COMMIT" \
    && make px4_sitl_default

WORKDIR /opt/px4
ENV PX4_SIM_MODEL=sihsim_quadx
EXPOSE 14540/udp 14550/udp
ENTRYPOINT ["/opt/px4/build/px4_sitl_default/bin/px4", "-d"]
