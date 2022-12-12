# Mailspoofsent

Mailspoofsent is a Bash script that sends an email using the mail-from and mail-envelope addresses specified by the user.

## Requirements

- Postfix
- Mailutils

## Usage

```bash
./mailspoofsent.sh --mail-from sender@example.com --mail-to recipient@example.com --mail-envelope envelope-sender@example.com --subject "Email subject" --body "Email body --spoof-domain "example.com"
```

To email with BCC option use:

```bash
./mailspoofsent.sh --bcc bcc@example.com --mail-from sender@example.com --mail-to recipient@example.com --mail-envelope envelope-sender@example.com --subject "Email subject" --body "Email body" --spoof-domain "example.com"
```

To show the usage information, run the script with the -h or --help option:

```bash
./mailspoofsent.sh -h
./mailspoofsent.sh --help
```

## Options

```
Usage: ./mailspoofsent.sh [--bcc bcc_address] --mail-from mail_from --mail-to mail_to --mail-envelope mail_envelope --subject subject --body body

Options:
  --bcc bcc_address   Specify a bcc address for the email
  --mail-from         The sender's email address
  --mail-to           The recipient's email address
  --mail-envelope     The envelope sender for the email
  --subject           The subject of the email
  --body              The body of the email
```

## Explanation

The mail-from address is the address that appears in the "From" field of the email and is the address that the recipient sees as the sender of the email. The mail-envelope address, on the other hand, is the address that is used as the actual sender of the email and is used by the mail server to route the email.

For example, if the mail-from address is sender@example.com and the mail-envelope address is envelope-sender@example.com, the recipient of the email will see that the email was sent from sender@example.com, but the mail server will use envelope-sender@example.com to route the email.

In some cases, the mail-from and mail-envelope addresses may be the same, but it is also common to use a different address for the mail-envelope to protect the identity of the real sender or to prevent the email from being marked as spam.

### Why mail configuration is so important?

#### DMARC

DMARC (Domain-based Message Authentication, Reporting and Conformance) is an email authentication protocol that is used to determine whether an email is likely to be legitimate or not. One of the checks that DMARC performs is to compare the mail-from and mail-envelope addresses in the email to see if they match.

If the mail-from and mail-envelope addresses match, it is a strong indication that the email is legitimate and not a spoofed email. However, if the addresses do not match, it may be an indication that the email is a spoofed email and should be treated with caution.

In order to perform this check, DMARC uses the DKIM (DomainKeys Identified Mail) and SPF (Sender Policy Framework) authentication methods to verify the authenticity of the email. If both of these authentication methods pass, DMARC will then compare the mail-from and mail-envelope addresses to determine if the email is likely to be legitimate.

Overall, the comparison of the mail-from and mail-envelope addresses is an important part of the DMARC email authentication process and helps to protect against spoofed emails.

#### SPF

SPF (Sender Policy Framework) is an email authentication method that is used to verify the identity of the sender of an email. SPF works by allowing the owner of a domain to specify which IP addresses are authorized to send email on behalf of that domain.

When an email is received, the receiving mail server can use the SPF record of the domain in the mail-envelope address to verify that the IP address of the sending server is authorized to send email for that domain. If the IP address is not authorized, the email may be flagged as spam or rejected.

However, it is important to note that SPF only checks the domain in the mail-envelope address, not the mail-from address. This means that an attacker could potentially bypass SPF checks by setting the mail-from address to a different domain than the mail-envelope address.

For example, if the mail-envelope address is envelope-sender@example.com and the SPF record for the example.com domain only allows emails to be sent from a specific set of IP addresses, an attacker could set the mail-from address to attacker@attack.com and still send an email that would pass the SPF check.

In order to prevent this type of attack, it is recommended to use additional email authentication methods, such as DKIM (DomainKeys Identified Mail) and DMARC (Domain-based Message Authentication, Reporting and Conformance), which can provide more robust protection against spoofed emails.

#### DKIM

DKIM (DomainKeys Identified Mail) and SPF (Sender Policy Framework) are two email authentication methods that are often used together with DMARC (Domain-based Message Authentication, Reporting and Conformance) to protect against spoofed emails.

DKIM works by adding a digital signature to the headers of an email, which can be used to verify the authenticity of the email. The digital signature is created using a private key that is held by the domain owner, and the corresponding public key is published in the domain's DNS records.

When an email is received, the receiving mail server can use the public key to verify the DKIM signature and determine if the email is likely to be legitimate. If the DKIM signature is valid, it indicates that the email has not been modified in transit and is likely to be legitimate.

#### Reverse DNS

The sending Mail Server IP (Received From IP) must match the IP of the domain in the Pointer (PTR) record, also known as the Reverse DNS record. The PTR record verifies that the sending domain is associated with that sending Mail Server IP.
