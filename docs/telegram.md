# Telegram cycle summary

GrantHound can post a one-line summary to a Telegram chat after every cycle
("GrantHound evaluated 20 programs. APPLY 1 / WATCH 1 / NEEDS REVIEW 11 /
PASS 7. runs run-... . <site url>"). It is entirely optional: if the
parameter below is not set, the runtime skips the notification and logs why.
It never fails a cycle, and it never sends the bot token anywhere except
Telegram's own API.

## 1. Make a bot with @BotFather

1. Open a chat with [@BotFather](https://t.me/BotFather) in Telegram.
2. Send `/newbot` and follow the prompts (name, then a username ending in
   `bot`).
3. BotFather replies with an HTTP API token, a string that looks like
   `123456789:AAExampleTokenDoNotUseThisOne`. Keep it secret; anyone who has
   it can send messages as your bot.

## 2. Get the chat id with `getUpdates`

1. Send any message to your new bot (or add it to a group and mention it).
2. Call `getUpdates` with the token from step 1:

   ```bash
   curl "https://api.telegram.org/bot<your-token>/getUpdates"
   ```

3. In the JSON response, find `message.chat.id` (a group chat id is
   negative, e.g. `-1002345678901`; a direct message to the bot is a
   positive user id). That number is your chat id.

## 3. Store `<token>|<chat id>` as an SSM SecureString

The runtime reads one parameter, named by the `GRANTHOUND_TELEGRAM_PARAM`
environment variable (default `/granthound/telegram`), whose value is the
token and chat id joined by a single `|`:

```bash
aws ssm put-parameter \
  --name /granthound/telegram \
  --type SecureString \
  --value "<your-bot-token>|<your-chat-id>" \
  --overwrite
```

Replace both placeholders with your own values — never commit a real token
or chat id to the repo, and never paste one into an issue or chat log.

## 4. What the runtime role needs

The AgentCore runtime role must be able to read and decrypt that one
parameter. Two statements, scoped to the parameter's ARN only (see
`agent/policies/store-access.json` for the exact policy this project uses):

```json
{
  "Effect": "Allow",
  "Action": ["ssm:GetParameter"],
  "Resource": "arn:aws:ssm:<region>:<account-id>:parameter/granthound/telegram"
},
{
  "Effect": "Allow",
  "Action": ["kms:Decrypt"],
  "Resource": "*",
  "Condition": {
    "StringEquals": {
      "kms:ViaService": "ssm.<region>.amazonaws.com",
      "kms:EncryptionContext:PARAMETER_ARN": "arn:aws:ssm:<region>:<account-id>:parameter/granthound/telegram"
    }
  }
}
```

`kms:Decrypt` is scoped with a `kms:ViaService` / `kms:EncryptionContext`
condition rather than a specific key ARN, because SSM SecureString
parameters are decrypted through the SSM service using the AWS-managed
`alias/aws/ssm` key by default; the condition keeps the grant to exactly
this one parameter, not every secret encrypted with that key.

## 5. A missing parameter is not an error

If `GRANTHOUND_TELEGRAM_PARAM` is unset, or the named parameter does not
exist, `notify_cycle` returns `"skipped: no GRANTHOUND_TELEGRAM_PARAM"` or
`"skipped: parameter not found"`. Either way this is a log line on the run
record, never a raised exception and never a failed cycle — an org can run
GrantHound with no Telegram bot at all and only use the web inbox and
`deadlines.ics`.
