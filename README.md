# Patient summary verification portal

A website where a research participant reads the AI-written summary of their
interview, marks each sentence right or wrong, and approves a corrected version.
What they approve is saved as the record.

Putting the website on a public address is the one piece nobody has decided on.


## How it works

1. The summary pipeline writes a file to
   `summaries/<patient_id>/<interview_id>.txt`.
2. That write triggers an email inviting the participant to the portal.
3. The participant enters their email address and gets a six-digit code by
   email. There is no password.
4. They mark each sentence right, wrong, or unsure, and say what was wrong.
5. An AI model rewrites only the flagged sentences. They review and approve.
6. The approved version is written separately. The original is never modified.

A participant can have several interviews and chooses which one to review.

Enrol a participant before their summary arrives, or there is no address to
send the invitation to.

Names used throughout:

- `patient_id` is the patient ID the study assigns, for example `EMORY-0042`.
- `interview_id` is the interview date, for example `2026-03-04`.
- The summary pipeline is whatever writes the summaries. Not part of this
  project.


## What the summary pipeline has to produce

One plain text file per interview, at exactly this key in the portal's bucket:

    summaries/<patient_id>/<interview_id>.txt

for example `summaries/EMORY-0042/2026-03-04.txt`. This layout is fixed in code.
A file written anywhere else is invisible: no email is sent, and the participant
signing in sees "your summary is not ready yet".

Both parts are validated, and a key failing either is ignored:

- `patient_id`: letters, digits, dot, underscore or hyphen, starting with a
  letter or digit, up to 64 characters. Case sensitive, and must match the
  roster exactly.
- `interview_id`: a date as `YYYY-MM-DD`. For a second interview the same day,
  append `-2`, giving `2026-03-04-2`.

The file is the summary as plain prose, UTF-8. No JSON, no header, no metadata.
It is split into sentences at sentence endings and line breaks, so anything on
its own line becomes its own item.

Do not rewrite a summary once it is written. Replacing the file leaves any
answers the participant has already given attached to the old sentences.


## Before you start

- An AWS account covered by a BAA.
- Git, Node.js 20 or newer, Python 3.11 or newer, and the AWS CLI.
- From the study team, needed only when going live: the data retention period
  and a contact address for participants.

Check what is installed. Each should print a version:

    git --version
    node --version
    python --version
    aws --version

Anything that errors is not installed. Download it, take the default options,
then close PowerShell and open it again before checking; a new install is not
visible in a PowerShell window that was already open.

- Git: https://git-scm.com/downloads
- Node.js: https://nodejs.org, the version labelled LTS
- Python: https://www.python.org/downloads/, and tick "Add python.exe to PATH"
  on the first screen of the installer
- AWS CLI: https://aws.amazon.com/cli/

Run every command in this document in **PowerShell**. Open it from the Start
menu. Each command is a single line however wide it looks here.

Every command says which folder to run it in. Almost all run from the
repository root, set up in step 1; the website runs from `web/`, a folder
inside it. Move between them with `cd`:

    cd web          repository root into web
    cd ..           back up to the repository root

`pwd` prints where you are.


## Get it running, with the website on your machine

This is the real system, with the website served from your machine instead of a
public address. After step 7 everything is set up and you can sign in.

### 1. Download the code and install what it needs

Open PowerShell and go to wherever you keep projects, for example:

    cd Documents

Download the code:

    https://github.com/ab712231/EmoryTranscribedInterviewVerifier.git

That creates a folder named `EmoryTranscribedInterviewVerifier`. Go into it:

    cd EmoryTranscribedInterviewVerifier

This folder is the repository root, and every instruction below is relative to
it.

Install the Python packages, from the repository root:

    python -m pip install -r requirements.txt

Then the website's packages:

    cd web
    npm install
    cd ..

The last line returns you to the repository root. `npm install` takes a minute
or two, and warnings are normal.

### 2. Sign in to the Emory account

Your AWS user needs administrator access to the account, because deploying
creates roles, a user pool, a bucket, an encryption key and email settings. If
you do not have it, ask whoever manages Emory's AWS accounts.

If the AWS CLI has never been signed in on this computer, set it up once, from
any folder. If you sign in to AWS through an Emory sign-in page:

    aws configure sso

Enter the address of that sign-in page and the region it asks for, sign in in
the browser window that opens, then choose the Emory account and your role.
When it asks for a profile name, type `emory`. Then, in the PowerShell window
you are working in:

    $env:AWS_PROFILE = "emory"

Run that line again in any new PowerShell window. If you were given an access
key instead, run the following and paste the key ID and secret when asked:

    aws configure

Confirm you are pointed at the right account:

    aws sts get-caller-identity

Everything deploys into the account this prints, so check it before step 4. If
a command later says your sign-in has expired, run `aws sso login`.

### 3. Configure it

This first deployment is configured by `infra/config/dev.json`. Open it in
Notepad. Three values are blank, and step 4 refuses to deploy until you type
them in. Leave the rest as it is:

- `region`: the AWS region to deploy into, written as a code like `us-east-1`.
  It must offer Claude Haiku 4.5 in Bedrock; `us-east-1` and `us-west-2` do.
- `sesFromAddress`: the address all portal email is sent **from**. It appears
  as the sender on the invitation, the sign-in code, and the notification to
  staff. AWS will email this address asking you to verify it, so it has to be
  one you can read.
- `studyTeamAddress`: the address that is notified **when a participant
  submits**. In the real study this is a shared staff mailbox. Participants
  never see it, and it never contains clinical text.

While testing, put your own address in both. Nothing here decides where the
participant's email goes; that comes from `roster.csv` in step 5.

The file should end up looking like this:

    {
      "envName": "dev",
      "region": "us-east-1",
      "stackPrefix": "PortalDev",
      "allowedOrigins": [
        "http://localhost:5173"
      ],
      "sesFromAddress": "your.name@emory.edu",
      "manageSesIdentity": true,
      "kmsKeyAlias": "alias/portal-dev-summaries",
      "studyTeamAddress": "your.name@emory.edu"
    }

### 4. Deploy it

From the repository root:

    python scripts/deployment/deploy.py --env dev

It works through the following in order, and stops at the first one that fails,
saying which. Every step is safe to repeat, so fix what it reported and run the
same command again. The first run takes about five minutes.

1. Checks `dev.json`.
2. Shows which AWS account it is about to use.
3. Prepares the account for deploying. This only does work once per account
   and region.
4. Makes one real call to Claude Haiku 4.5 in Bedrock, which switches the model
   on for the account. If it reports that a use case form is needed, submit it
   from the model catalog in the Bedrock console, then run again.
5. Deploys. If it asks to approve permissions, answer `y`. It only asks when
   permissions change, so a repeat run may not ask at all.
6. Points the website at what was deployed.
7. Prints what was created.

On the first run, AWS emails the `sesFromAddress` from `dev.json` asking you to
verify it. Click the link, checking spam if it does not arrive. Nothing sends
until you do.

To print what was created again later, from the repository root:

    python scripts/deployment/stack_outputs.py --env dev

### 5. Enrol the participants

`roster.csv` is the list of who can sign in, and the only place participant
email addresses are held. Build it in Excel or Google Sheets:

1. Open a new blank spreadsheet.
2. In cell A1 type `patient_id`. In B1 type `email`. Spell them exactly that
   way, lower case, with the underscore.
3. Fill one row per participant underneath: the patient ID in column A, their
   email address in column B. No blank rows between them.
4. Save it as CSV. In Excel: File, then Save As, then change "Save as type" to
   **CSV UTF-8 (Comma delimited)**. In Google Sheets: File, then Download, then
   **Comma-separated values**.
5. Put the file in the repository root and name it `roster.csv`.

Opened in a text editor, it should look exactly like this:

    patient_id,email
    EMORY-0042,jordan.rivera@emory.edu
    EMORY-0043,sam.okafor@emory.edu

While testing, put your own email address on one row, against the `patient_id`
the pipeline will write for your test interview in step 6. SES delivers to
nothing else until you request production access, so that is the only row you
can sign in as.

Two things to get right:

The `patient_id` must match what the pipeline writes, character for
character. It is case sensitive: `emory-0042` is not `EMORY-0042`.

Each email address may appear once, and each `patient_id` once. Two people
cannot share an inbox, because the address is how someone signs in.

If the study already keeps this list in a spreadsheet, export that instead of
retyping it. Extra columns, capitalised headings, and trailing blank rows are
all ignored, so it usually works unedited as long as two columns are named
`patient_id` and `email`.

`roster.csv` stays on your machine and is gitignored.

Check it. From the repository root:

    python scripts/provision_users/provision.py --env dev --roster roster.csv --dry-run

It changes nothing and runs the same checks as the real thing, so a clean dry
run means a clean run. Until step 6 it lists everyone under "no summary in the
bucket yet", which is expected. Fix anything else it reports first. An ID
differing only by capitalisation cannot be corrected later without deleting the
account.

Remove `--dry-run` to create the accounts. Nobody can sign in until this runs.
If any row is rejected it says so and exits non-zero, so check that rather than
assuming it worked.

Rerun it with the full list whenever new participants join; existing ones are
left alone.

### 6. Connect the summary pipeline

Point the pipeline at the `SummariesBucketName` printed in step 4, writing files
in the format given in "What the summary pipeline has to produce" above.

Its AWS role needs permission to write there. From the repository root:

    python scripts/deployment/stack_outputs.py --env dev --pipeline-policy

That prints the exact IAM policy, with this deployment's names filled in.

Have it write one interview, then check it landed. From the repository root:

    python scripts/roster_status/status.py --env dev

The interview should be listed under its `patient_id` and date, as
`not started`. If it says `not enrolled`, its `patient_id` does not match
`roster.csv` exactly. If it is missing, or the ID or date is not what you
expect, fix that before going further.

If the pipeline is not ready yet, put one summary in yourself to carry on. Write
a few sentences of summary text into `summary.txt` in the repository root, then,
from the repository root:

    python scripts/summaries/put_summary.py --env dev --patient-id EMORY-0042 --interview-id 2026-03-04 --file summary.txt

It checks the ID and date the same way the portal does, and refuses to replace a
summary that already exists. `summary.txt` is gitignored.

### 7. Run the website and sign in

Step 4 already pointed the website at this deployment. From `web/`:

    npm run dev

Open `http://localhost:5173`. Ctrl+C stops the server.

Signing in as the participant from `roster.csv` should go like this:

1. "Check your interview summary" asks for an email address. Enter the one in
   `roster.csv`.
2. An email titled "Your sign-in code" arrives from the `sesFromAddress` in
   `dev.json`. Type the six-digit code into "Enter your code".
3. "Read your interview summary" shows the summary from step 6. A participant
   with more than one sees "Your interview summaries" first, to choose one.
4. "Check each statement" asks about every sentence: "Yes, that's right", "No,
   that's not right" or "I'm not sure". Choosing no asks what it should say.
5. "Check the corrected version" shows the summary with those sentences
   rewritten. Choose "Approve and submit".
6. "Thank you, you're all done" appears. An email titled "Summary verification
   submitted" reaches the `studyTeamAddress`, and `status.py` from step 6 shows
   the interview as `submitted`.

Separately, once the summary is written in step 6, the participant's inbox gets
an email titled "Your interview summary is ready to check". That is the
invitation real participants receive.

## Running the study

There is no admin website. These scripts need a checkout of this repository
and AWS credentials, and run from the repository root. They use `--env dev`
while testing; change it to `--env prod` once the study is live.

If a participant is not receiving codes, first check the address they are
typing matches their row in the roster. Then check SES is able to send:

    python scripts/deploy_preflight/check_ses.py --env dev

If both look right, the CreateAuthChallenge logs in CloudWatch show whether a
code was issued. There is no lockout to clear.

To reopen a submitted session. Archives what they approved first:

    python scripts/unlock_session/unlock.py --env dev --patient-id EMORY-0042 --interview-id 2026-03-04 --reason "Participant called: wrong medication dose" --operator "Your Name" --dry-run

Drop `--dry-run` to apply. `status.py` from step 6 lists the IDs and dates.

## Getting the results out

Both commands run from the repository root.

### The results spreadsheet

    python scripts/analyze_verifications/analyze.py --env dev --csv results.csv

That writes `results.csv`, which opens in Excel, with one row per sentence a
participant reviewed. For one participant only, add their ID:

    python scripts/analyze_verifications/analyze.py --env dev --csv results.csv --patient EMORY-0042

The columns:

- `patient_id` and `interview_id` say whose interview it is.
- `status` is `submitted` once they approved their corrected version. Anything
  else means they have not finished, so their answers may still change.
- `statement_number` counts the sentences of the summary from 1, the same
  numbers the website shows.
- `statement_text` is the sentence as the AI wrote it.
- `verdict` is what they said about it: `correct`, `incorrect` or `unsure`.
- `note` is what they typed when they marked it wrong, in their own words.
- `outcome` says what the corrected version did with a sentence marked
  `incorrect`: `rewritten`, `removed` or `not applied`. `not applied` means the
  AI could not make that correction, so the sentence stayed as written.
- `corrected_text` is what a `rewritten` sentence became, or `(removed)`.

`outcome` and `corrected_text` are blank for every other sentence, and until the
participant has asked for their corrected version.

It also prints two accuracy figures, one excluding "not sure" answers and one
counting them against the AI. Choose knowingly when writing this up.

### The summaries themselves

To save every original and approved summary into a folder on this machine:

    python scripts/analyze_verifications/analyze.py --env dev --download results

`results/originals/` holds what the AI wrote, which is never modified.
`results/approved/` holds what each participant approved, which is the study
record. It only has an interview once the participant has submitted.

If a coordinator has reopened a session, the version the participant approved
first is kept under `approved/superseded/`, named with the date it was replaced.
