# Use the official Kong image as a base
FROM kong:3.7

# Copy the custom configuration file into the image
# This allows you to manage configuration via a file instead of only environment variables.
COPY kong.conf /etc/kong/kong.conf

# You can add more customizations below, such as installing custom Kong plugins.

# Set the default command to use our custom config
CMD ["kong", "docker-start", "--conf", "/etc/kong/kong.conf"]
