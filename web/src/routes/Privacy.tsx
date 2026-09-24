import { Link } from "react-router-dom";
import { AppLayout } from "../components/layouts";
import { STUDY } from "../studyConfig";
import "./privacy.css";


export function Privacy() {
  return (
    <AppLayout documentTitle="How your information is used">
      <h1 className="page__title">How your information is used</h1>
      <p className="page__lede">
        This page explains what this website holds about you, who can see it,
        and how it is kept safe. It is written for you, not for lawyers.
      </p>

      <div className="panel policy">
        <section className="policy__section">
          <h2 className="policy__heading">What this site holds about you</h2>
          <ul className="policy__list">
            <li>Your email address, which the study team already had.</li>
            <li>
              Nothing else that identifies you. There is no password, and
              nothing for you to remember.
            </li>
            <li>The summary written after your interview.</li>
            <li>
              Your answer to each sentence: right, not right, or not sure.
            </li>
            <li>Anything you type in the box explaining what was wrong.</li>
            <li>The corrected summary, once you approve it.</li>
            <li>The dates and times you did these things.</li>
          </ul>
          <p>
            What you type is kept exactly as you wrote it. It is not tidied up
            or reworded, because your own words are what the study is studying.
          </p>
        </section>

        <section className="policy__section">
          <h2 className="policy__heading">What this site does not do</h2>
          <ul className="policy__list">
            <li>It does not use cookies to follow you around the internet.</li>
            <li>
              It has no advertising and no analytics. No other company receives
              anything about your visit.
            </li>
            <li>Your information is never sold or shared for marketing.</li>
            <li>
              It does not ask for or keep your date of birth. Signing in uses a
              code we email you at the time, so there is nothing stored here
              that could be stolen and reused.
            </li>
            <li>
              It will never ask for your Social Security number or for payment.
              If a page claiming to be this study asks for either, it is not us.
            </li>
          </ul>
        </section>

        <section className="policy__section">
          <h2 className="policy__heading">Who can see your answers</h2>
          <p>
            The study team at Emory. That is the whole list of people who read
            what you write.
          </p>
          <p>
            No other participant can see your record. Signing in shows you only
            your own summary; the site cannot show you anyone else&rsquo;s.
          </p>
          <p>
            Amazon Web Services stores the information for us, under an
            agreement that covers health information. Their staff do not read
            it.
          </p>
        </section>

        <section className="policy__section">
          <h2 className="policy__heading">How the corrected wording is made</h2>
          <p>
            When you mark a sentence as not right and explain why, we use an AI
            service to rewrite that one sentence to match what you told us. It
            is worth being precise about what this involves.
          </p>
          <ul className="policy__list">
            <li>
              We send the single sentence you flagged and the note you wrote.
              Your name, your email address, and the rest of your summary are
              not sent.
            </li>
            <li>
              The AI runs inside the study&rsquo;s own Amazon account, on
              computers in the United States.
            </li>
            <li>
              Amazon states that it does not store these requests, does not use
              them to train AI models, and does not share them with anyone else.
            </li>
            <li>
              The AI is only allowed to change wording. It is instructed not to
              add anything you did not say, and the result is checked before you
              see it.
            </li>
            <li>
              Nothing is recorded until you read the corrected version and
              approve it. If you do not approve it, it is not kept.
            </li>
          </ul>
        </section>

        <section className="policy__section">
          <h2 className="policy__heading">How your information is protected</h2>
          <ul className="policy__list">
            <li>
              Signing in needs a code we email you at that moment. Because it is
              sent when you ask for it, an old email is of no use to anyone.
            </li>
            <li>
              A code works once and only for a few minutes. Getting it wrong
              ends the attempt and you ask for a new one, so it cannot be
              guessed at repeatedly.
            </li>
            <li>
              You are signed out when you close the tab. Nothing about your
              record is left on your device afterwards.
            </li>
            <li>
              Your information travels over an encrypted connection and is
              stored encrypted, with a key that belongs to the study.
            </li>
            <li>
              The original summary is never overwritten. Your corrections are
              saved separately, so what was originally written can always be
              compared with what you approved.
            </li>
          </ul>
        </section>

        <section className="policy__section">
          <h2 className="policy__heading">How long it is kept</h2>
          <p>
            Your information is kept for {STUDY.retentionPeriod}.
          </p>
        </section>

        <section className="policy__section">
          <h2 className="policy__heading">Your choices</h2>
          <p>
            Taking part is voluntary. You can stop at any point, and you do not
            have to give a reason.
          </p>
          <p>
            You can approve a summary even if you are not sure about parts of
            it. Marking something &ldquo;not sure&rdquo; is a real answer and is
            useful to the study.
          </p>
          <p>
            Once you approve a summary you cannot change it on this site. If you
            realise afterwards that something is wrong, contact the study team
            and they can reopen it for you.
          </p>
        </section>

        <section className="policy__section">
          <h2 className="policy__heading">Questions</h2>
          <p>
            Contact the study team at {STUDY.studyTeamContact}, or use the details
            in the email that brought you here.
          </p>
        </section>
      </div>

      <p className="policy__back">
        <Link to="/">Back to sign in</Link>
      </p>
    </AppLayout>
  );
}
