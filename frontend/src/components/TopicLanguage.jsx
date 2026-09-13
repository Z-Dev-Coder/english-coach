import Glossed from "./Glossed";
import { cx } from "../lib/cx";
import Icon from "../lib/icons";

/**
 * The vocabulary, expressions and tips to learn before an exercise.
 *
 * Shared by listening and Talk so both teach the same way. Pass `used` (a list
 * of item texts) to show which ones the learner has already put to use.
 */

function Items({ title, items, used }) {
  if (!items?.length) return null;
  return (
    <section className="mt-4">
      <h3 className="micro">{title}</h3>
      <ul className="mt-2 grid gap-2 sm:grid-cols-2">
        {items.map((item) => {
          const done = used?.includes(item.text);
          return (
            <li
              key={item.text}
              className={cx(
                "rounded-xl bg-sunken p-3 dark:bg-white/[0.04]",
                done && "ring-1 ring-[color:var(--color-good-ink)]/40",
              )}
            >
              <p className="flex items-center gap-1.5 font-semibold">
                {done && <Icon name="check" size={13} className="text-[color:var(--color-good-ink)]" />}
                {item.text}
              </p>
              <Glossed as="p" className="mt-0.5 text-[14px] text-ink-2 dark:text-white/70">
                {item.meaning}
              </Glossed>
              {item.example && (
                <p className="mt-1 border-l-2 border-[color:var(--color-line)] pl-2.5 text-[13px] italic text-ink-3">
                  {item.example}
                </p>
              )}
            </li>
          );
        })}
      </ul>
    </section>
  );
}

export default function TopicLanguage({ language, used, questionsTitle = "listen for these" }) {
  if (!language) return null;
  const empty = !language.vocabulary?.length && !language.expressions?.length;

  return (
    <div>
      {language.is_fallback && empty && (
        <p className="text-[13px] text-ink-3">
          The AI mentor isn&rsquo;t reachable, so there&rsquo;s no topic vocabulary this time.
        </p>
      )}
      <Items title="words for this topic" items={language.vocabulary} used={used} />
      <Items title="expressions to use" items={language.expressions} used={used} />

      {language.questions?.length > 0 && (
        <section className="mt-4">
          <h3 className="micro">{questionsTitle}</h3>
          <ol className="mt-1.5 list-decimal space-y-1 pl-5 text-[14px]">
            {language.questions.map((question) => (
              <li key={question}>{question}</li>
            ))}
          </ol>
        </section>
      )}

      {language.tips?.length > 0 && (
        <section className="mt-4">
          <h3 className="micro">tips</h3>
          <ul className="mt-1.5 list-disc space-y-1 pl-5 text-[14px] text-ink-2 dark:text-white/70">
            {language.tips.map((tip) => (
              <li key={tip}>{tip}</li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
