# Quality algorithm

## The problem this solves

Older prompts told the model to "make it professional" while also demanding
that the source tone and length be preserved almost exactly. Weak or small
models interpreted this as plain proofreading: they fixed capitals, commas,
and dashes but left profanity, slang, grammar errors, and broken logic intact.

## The pipeline

1. The model first determines the factual meaning and communicative goal.
2. It rewrites the source in the selected register.
3. Business mode explicitly requires removing profanity, shouting, street
   slang, filler, and aggressive calls, and repairing grammar and logic so the
   text is ready to send.
4. The natural translation is built from the already-edited source, not the
   raw text.
5. A local module checks whether the model repeated the noisy text almost
   verbatim.
6. If the result is weak, one strengthened retry request is made.
7. Of the two responses, the one that passes quality control better is chosen.
8. If the retry technically fails, the first response is never lost.

## What counts as a weak result

- a requested result field is empty;
- the business variant is too close to the noisy source;
- the business variant retained profanity;
- the business variant retained source slang;
- the friendly variant repeated clearly broken text almost verbatim;
- short-reply mode did not shorten a long message.

## Control example

Source:

`мама мыла раму! ну и чо такого спросил я ее. да пошла ты хочу узнать скоклько время сейчас слышь?`

Weak result that is now rejected:

`Мама мыла раму! Ну и чё такого — спросил я её. Да пошла ты, хочу узнать, сколько время сейчас, слышь?`

Expected business result:

`Мама мыла раму. Я спросил, что в этом необычного, а затем уточнил, который сейчас час.`

## Important limitation

Quality still depends on the selected language model. The automatic retry pass
significantly reduces the chance of punctuation-only "pseudo-editing" but
cannot make a weak model equal to a strong one. For complex texts, choose a
model with good Russian, English, and Hebrew support.
