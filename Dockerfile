# Use the latest version of Alpine as the base image
FROM ubuntu:latest

# Install Postfix and Mailutils
RUN echo "postfix postfix/mailname string example.com" | debconf-set-selections
RUN echo "postfix postfix/main_mailer_type string 'Internet Site'" | debconf-set-selections
RUN apt update && apt install postfix mailutils git -y

# Clone the mailspoofsent repository from GitHub
RUN cd /
RUN git clone https://github.com/mverschu/mailspoofsent

# Set the working directory to the mailspoofsent directory
WORKDIR /mailspoofsent
RUN chmod +x ./mailspoofsent.sh

# Run the mailspoofsent program when the container is started
CMD ["/mailspoofsent/mailspoofsent.sh"]
