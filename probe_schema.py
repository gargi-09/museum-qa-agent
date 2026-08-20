"""
probe_schema.py -- Confirms api_client.py's wire format against the real
endpoint before any real-budget run, for the smallest possible number of
billed tokens.

Status of the three values, after reading the brief's §3 client example
(json={"messages", "max_tokens", "temperature"}):
    1. SEND_MODEL_FIELD -- RESOLVED BY THE BRIEF. The documented payload has
       no 'model' field, and §5 says "There's no model to choose." Default is
       now 0. STEP 1 CONFIRMS this rather than discovering it.
    2. MODEL_NAME       -- MOOT while (1) holds. STEP 2 only runs if the
       endpoint contradicts the brief by demanding a model.
    3. MESSAGE_FORMAT   -- BOTH separate placements measured as DROPPED on
       live dev runs. prompt_tokens stayed at 8 for a bare "hi", for the same
       message plus a ~13-token top-level "system" key, and again for the same
       message plus a {"role": "system"} entry in messages. The instruction
       text was never billed as input either way, and the model returned an
       identical generic greeting instead of obeying a plain "reply with
       exactly CORTEX_OK". Two signals agreeing: this proxy discards a
       separately-supplied system prompt. STEP 4 tests the remaining
       placement, "prepend" -- instructions folded into the user message.

WHY SEQUENTIAL ISOLATION, not one combined call: a single probe carrying both
a guessed model AND a guessed system placement cannot tell you which one a
400 rejected. If MODEL_NAME were wrong, BOTH message formats would return
400, and the obvious-but-wrong conclusion is "neither format is accepted" --
sending you off to mutate a format that was already correct while the actual
culprit sits untouched. So each step introduces exactly ONE new value, and
stops as soon as a step fails.

STEP 1 sends the brief's documented payload minus the system prompt -- no
guesses in it at all. A 200 confirms the documented shape is accepted and that
no 'model' field is needed, leaving system placement as the only open
question, which is what makes STEP 3's result unambiguous.

DEV MODE: every call sends X-Cortex-Mode: dev, matching call_haiku(dev_mode=
True). DEV_MODE MUST REMAIN True FOR THIS PROBE UNDER ALL CIRCUMSTANCES. THERE
IS NO COST-SAVING REASON TO DISABLE IT. Dev calls bill the free 50,000-token
dev sandbox; non-dev calls bill the real 200,000-token submission budget. So
running this script in dev mode costs ZERO real budget no matter how many
attempts it takes, and disabling dev mode could only ever make it cost more.

Dev mode is also confirmed SAFE for schema resolution. The assignment brief
states outright: "Nothing is truncated in dev, so whatever you build to catch
it won't get a chance to fire there." The injected silent truncation therefore
cannot fire on these calls.

A NOTE ON WHAT THAT DOES AND DOES NOT MEAN, because getting this wrong cost a
run. The brief's guarantee is about the INJECTED fault. It is not a promise
that a reply will never stop early for ordinary reasons -- a model will still
run into whatever max_tokens ceiling the caller sets. An earlier version of
this script conflated the two under one flag named "cut_off", saw
completion_tokens == max_tokens at a 16-token cap, and concluded the brief was
wrong about its own sandbox. It was not; the cap was just far too small. The
flag is now named hit_cap, is advisory only, and CANNOT block a verdict --
because delivery is established from prompt_tokens, which nothing on the
output side can affect.

A NOTE ON prompt_tokens AS AN INSTRUMENT. STEP 3's verdict depends entirely on
prompt_tokens being a faithful count of input. That was assumed, not checked --
and a counter that is stubbed, or computed only over the user turn, would
produce a delta of 0 for a system prompt that actually arrived, giving exactly
the reading STEP 3 saw. STEP 4 closes that hole as a side effect: it sends a
LONGER USER MESSAGE, which any honest input counter must register. If
prompt_tokens rises there but not in STEP 3, the counter is real and STEP 3's
drop was real. If it does not rise even there, prompt_tokens is not measuring
input on this endpoint, every delta above was uninformative, and the canary in
the reply becomes the only usable evidence. The script says which case it is
rather than presenting one as the other.

TOKEN COST: zero against the real 200,000-token submission budget, because
every call here is a dev call. Against the free 50,000-token dev sandbox: two
calls (~40 tokens) when a placement resolves early, three (~75) when STEP 4 is
needed. A rejected request bills nothing at all since it never reaches
inference. Measured on live runs: 37 and 45 tokens.

Usage (deliberately requires an explicit flag so it cannot run by accident):
    python probe_schema.py --yes
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

try:
    import requests
except ImportError:
    print("'requests' is not installed -- run: pip install requests")
    sys.exit(1)

from api_client import (check_credentials, extract_content_text, MODEL_NAME,
                        classify_status, TEMPERATURE)

CANARY = "CORTEX_OK"
CANARY_SYSTEM = f"Reply with exactly the word {CANARY} and nothing else."

# Matches the brief's own client example and api_client's
# REQUEST_TIMEOUT_SECONDS. A short timeout here would risk reporting a
# TERMINAL network failure for a call that was merely slow.
TIMEOUT = 180

# DEV_MODE must remain True for this probe under all circumstances. There is
# no cost-saving reason to disable it.
#
# Dev calls bill the free 50,000-token dev sandbox; non-dev calls bill the real
# 200,000-token submission budget. Dev mode is therefore strictly cheaper here
# in every scenario, including one where the probe needs several attempts to
# get a clean read -- several free attempts still cost zero real budget.
#
# Dev mode is also confirmed not to interfere with what this script resolves.
# Per the assignment brief: "Nothing is truncated in dev, so whatever you build
# to catch it won't get a chance to fire there." The INJECTED silent truncation
# cannot occur on these calls. That is not the same as "the reply will never
# stop early" -- a model still runs into whatever max_tokens the caller sets,
# which is what actually happened on the first live run. See CANARY_MAX_TOKENS.
DEV_MODE = True

# Canary cap. 64, not 16. A live run at 16 had the model spend the whole
# ceiling on "# Hey there! ...How's it going? What can I" -- it never got to
# the instruction, and the probe then misread its own tiny cap as evidence of
# endpoint truncation. max_tokens is a CEILING, not a charge, so headroom is
# free and there was never a reason to be stingy with it.
CANARY_MAX_TOKENS = 64

# Minimum prompt_tokens increase that counts as "the system prompt was
# delivered". CANARY_SYSTEM is ~13 tokens, so a real delivery should move the
# count by roughly that much; 5 is a floor that clears tokeniser noise and any
# small per-message template overhead without needing the exact figure. A live
# run measured 8 -> 8 (delta 0) for the top-level form, i.e. nowhere near this.
SYSTEM_DELIVERY_MIN_DELTA = 5

# Terminal conditions -- no point burning further attempts on any of these.
FATAL = {"bad_key", "budget_exhausted"}

_billed_calls = []


def send(payload, label):
    """One raw POST. Deliberately does NOT go through call_haiku(): the point
    is to control the exact payload shape per step, and call_haiku() applies
    the very module-level guesses this script exists to verify.

    Returns a dict with keys: status, error_type, content, hit_cap, detail,
    prompt_tokens.
    A dict rather than a tuple specifically so `detail` (the server's own
    rejection text) is available to the STEP 1 decision logic -- without it,
    a 400 cannot be told apart from a 404 or a 500, and every non-200 would
    have to be treated identically.
    """
    endpoint = os.getenv("CORTEX_MODEL_ENDPOINT")
    headers = {
        "Authorization": f"Bearer {os.getenv('CORTEX_API_KEY')}",
        "Content-Type": "application/json",
    }
    if DEV_MODE:
        headers["X-Cortex-Mode"] = "dev"
    print(f"\n--- {label} ---")
    print(f"    payload keys : {sorted(payload.keys())}")
    print(f"    message roles: {[m.get('role') for m in payload.get('messages', [])]}")

    print(f"    dev header   : {headers.get('X-Cortex-Mode', '(not sent)')}")

    try:
        resp = requests.post(endpoint, headers=headers, json=payload, timeout=TIMEOUT)
    except requests.exceptions.RequestException as e:
        # Covers connect errors, DNS failures, and TIMEOUTS. status stays None,
        # which STEP 1 treats as terminal -- a timeout is not evidence about
        # any schema guess.
        print(f"    NETWORK FAILURE: {e}")
        return {"status": None, "error_type": "network_error", "content": None,
                "hit_cap": False, "detail": str(e), "prompt_tokens": None}

    error_type, _ = classify_status(resp.status_code)
    body_text = (resp.text or "")[:600]
    print(f"    HTTP {resp.status_code}"
          + (f"  ({error_type})" if error_type else "  (ok)"))

    if resp.status_code != 200:
        # Rejected before inference -- free. The body is the whole point.
        print(f"    server said  : {body_text}")
        return {"status": resp.status_code, "error_type": error_type,
                "content": None, "hit_cap": False, "detail": body_text,
                "prompt_tokens": None}

    try:
        data = resp.json()
    except ValueError:
        # HTTP 200 with a body we cannot parse. error_type is set, and STEP 1
        # checks error_type as well as status precisely so this cannot be
        # mistaken for a clean success.
        print(f"    200 but body is not JSON: {body_text}")
        return {"status": resp.status_code, "error_type": "invalid_json_response",
                "content": None, "hit_cap": False, "detail": body_text,
                "prompt_tokens": None}

    content = extract_content_text(data.get("content"))
    usage = data.get("usage")
    if usage:
        _billed_calls.append(usage)

    # Did the reply stop because it hit OUR max_tokens ceiling?
    #
    # NAMED hit_cap, NOT cut_off, because the previous name caused a real
    # misdiagnosis. A live run with max_tokens=16 returned
    # "# Hey there! ...How's it going? What can I" at completion_tokens=16,
    # and the probe reported that the brief must be wrong about dev-mode
    # truncation. It is not. The brief's claim is that nothing is SILENTLY
    # truncated in dev -- that is the injected fault. A model running into a
    # ceiling the caller chose is an ordinary, self-inflicted stop and tells
    # you nothing about the injected fault. Two different things; conflating
    # them under one name led straight to the wrong conclusion.
    #
    # This flag is now advisory only. It qualifies how much weight to put on
    # an absent canary, and it must NOT block a delivery verdict, because
    # delivery is established from prompt_tokens (see STEP 3) which output
    # truncation cannot affect.
    #
    # NOT reusing api_client.detect_truncation() here, deliberately. Its
    # text-shape signals are calibrated for prose and JSON, and "CORTEX_OK"
    # ends in "K" -- so Signal 3 (no terminal punctuation) would fire on a
    # perfectly complete canary and report truncation that did not happen.
    stop_reason = data.get("stop_reason") or data.get("finish_reason")
    cap = payload.get("max_tokens")
    out = (usage or {}).get("completion_tokens") or (usage or {}).get("output_tokens")
    hit_cap = bool(stop_reason in ("max_tokens", "length")
                   or (out and cap and out >= cap))

    # Input-side token count. THE primary evidence for whether a system prompt
    # actually reached the model: if the text was part of the prompt it is
    # billed as input, and if it was dropped by the proxy it is not. Immune to
    # anything that happens to the output.
    prompt_tokens = (usage or {}).get("prompt_tokens")
    if prompt_tokens is None:
        prompt_tokens = (usage or {}).get("input_tokens")

    print(f"    top-level keys: {sorted(data.keys())}")
    print(f"    usage        : {usage}")
    print(f"    prompt_tokens: {prompt_tokens}   (input side -- delivery evidence)")
    print(f"    stop_reason  : {stop_reason!r}   hit_cap={hit_cap} (advisory only)")
    print(f"    budget_remaining: {data.get('budget_remaining')!r}  "
          f"<-- CHECK THE UNITS, see interpret_budget_remaining()")
    print(f"    content      : {content!r}")
    return {"status": resp.status_code, "error_type": None, "content": content,
            "hit_cap": hit_cap, "detail": None, "prompt_tokens": prompt_tokens}


def minimal_messages():
    return [{"role": "user", "content": "hi"}]


def base_payload(max_tokens):
    """The brief's documented payload minus the system prompt: exactly
    {"messages", "max_tokens", "temperature"}. Including temperature matters --
    the point of STEP 1 is to test the payload PRODUCTION actually sends, and
    api_client.build_payload() sends it. A probe that omitted it could pass on
    a shape the real pipeline never uses.
    """
    return {"messages": minimal_messages(), "max_tokens": max_tokens,
            "temperature": TEMPERATURE}


def rejection_blames_model(detail):
    """Does this rejection body actually blame the 'model' field?

    Deliberately a HEURISTIC, and deliberately used in the permissive
    direction only: a match merely ALLOWS step 2 to run, it never concludes
    anything on its own, and step 2's result is judged independently. A body
    that does not mention 'model' stops the probe instead of advancing it,
    which is the safe direction -- the alternative (advancing on every
    rejection) is what previously let a 404 or a 500 be misread as
    "the model field is required".

    The raw body is always printed, so a human can overrule this.
    """
    return bool(detail) and "model" in detail.lower()


def main():
    if "--yes" not in sys.argv:
        print(__doc__)
        print("Refusing to run without --yes. This sends real requests to the")
        print("endpoint -- billed to the free dev sandbox, not the 200,000-token")
        print("submission budget, but still not a no-op.")
        return 1

    if not check_credentials():
        print("\nCredentials missing -- nothing was sent, no tokens spent.")
        return 1

    if not DEV_MODE:
        # Guard rather than comment: disabling dev mode makes every call below
        # bill the real submission budget for zero benefit. See DEV_MODE above.
        print("\nREFUSING TO RUN with DEV_MODE=False. Every call would bill the real")
        print("200,000-token submission budget instead of the free dev sandbox, and")
        print("this script gains nothing from it. Set DEV_MODE=True.")
        return 1

    print("=" * 72)
    print("STEP 1 -- zero guesses: no 'model', no 'system'")
    print("Determines whether a model field is required AT ALL.")
    print("=" * 72)
    r1 = send(base_payload(5), "minimal payload")
    status, err = r1["status"], r1["error_type"]
    # Baseline for STEP 3's delivery test: prompt_tokens for this user
    # message with NO system prompt attached.
    baseline_prompt_tokens = r1["prompt_tokens"]

    # ---- STEP 1 outcome triage -------------------------------------------
    # Every non-200 outcome is NOT equivalent, and treating them as equivalent
    # was a real bug: the old code sent every rejection into step 2, so a 404
    # from a wrong endpoint URL, a transient 500, a 429, or a 400 blaming an
    # unrelated field (e.g. max_completion_tokens) all ended up reported as
    # "the model field is required but the value was rejected". Each of the
    # branches below now terminates instead, except the one case that actually
    # licenses step 2.

    if status is None:
        # Network failure or TIMEOUT -- no information about any guess.
        print("\nTERMINAL: could not reach the endpoint (network error/timeout).")
        print("Check CORTEX_MODEL_ENDPOINT. Nothing was billed, nothing resolved.")
        return 1

    if err in FATAL:
        print(f"\nTERMINAL: {err}. Stopping -- further probing would be pointless.")
        return 1

    send_model = None

    if status == 200 and err is None:
        # Clean 200 AND a body that parsed as JSON -- see the err check. A 200
        # whose body failed to parse sets err='invalid_json_response' in send()
        # and is handled by the next branch, so it can never reach here.
        send_model = False
        print("\n=> RESOLVED: no 'model' field required. This ELIMINATES both the")
        print("   SEND_MODEL_FIELD and MODEL_NAME guesses -- not just verifies them.")

    elif status == 200:
        # HTTP 200 but the body did not parse. Concluding "model not required"
        # from a response we could not read would be exactly the
        # absence-of-error-as-success trap.
        print(f"\nTERMINAL: HTTP 200 but the body did not parse ({err}).")
        print("Refusing to conclude 'no model field required' from a response that")
        print("could not be read. Check the body printed above -- an HTML login or")
        print("proxy page here usually means CORTEX_MODEL_ENDPOINT is wrong.")
        return 1

    elif status == 429 or err == "server_error":
        # Transient upstream trouble says nothing about the schema.
        print(f"\nTERMINAL: {err} (status {status}) -- a transient upstream failure,")
        print("not evidence about any schema guess. Re-run later; this is free in")
        print("dev mode.")
        return 1

    elif status == 400 and rejection_blames_model(r1["detail"]):
        # THE ONLY path that licenses step 2.
        print("\n   Rejected with a 400 that mentions 'model' -- so the model field")
        print("   is plausibly required. Step 2 tests the guessed value. (Confirm")
        print("   against the body printed above.)")
        print()
        print("=" * 72)
        print(f"STEP 2 -- introduce exactly ONE guess: model={MODEL_NAME!r}")
        print("=" * 72)
        r2 = send(dict(base_payload(5), model=MODEL_NAME),
                  "minimal payload + model")
        if r2["error_type"] in FATAL:
            print(f"\nTERMINAL: {r2['error_type']}. Stopping.")
            return 1
        if r2["status"] == 200 and r2["error_type"] is None:
            send_model = True
            print(f"\n=> RESOLVED: 'model' is required and {MODEL_NAME!r} is accepted.")
        else:
            print("\n=> UNRESOLVED: the model field is required but this attempt did")
            print("   not cleanly succeed. Read the server message above -- these")
            print("   APIs usually name the valid values. Set CORTEX_MODEL and")
            print("   re-run. Stopping rather than guessing again.")
            return 1

    else:
        # Everything else: 404 (wrong endpoint path), a 400 blaming a field
        # other than 'model' (e.g. max_completion_tokens), or any other
        # unexpected status. NONE of these license step 2 -- the remaining
        # steps all assume this baseline shape is otherwise accepted, and it
        # demonstrably is not. Stop and let a human read the body.
        print(f"\nTERMINAL: status {status} ({err}), and the body does not blame the")
        print("'model' field. This baseline payload contains no guesses at all, so a")
        print("rejection here means something more fundamental is wrong than any of")
        print("the three values this script resolves:")
        print("  - 404          -> CORTEX_MODEL_ENDPOINT path is wrong")
        print("  - 400, other   -> a different required/renamed field, e.g.")
        print("                    'max_completion_tokens' instead of 'max_tokens'")
        print("Fix that first. NOT continuing to step 2: adding a 'model' field")
        print("cannot fix any of these, and a second identical rejection would")
        print("look exactly like a bad CORTEX_MODEL value.")
        return 1

    print()
    print("=" * 72)
    print("STEP 3 -- does the system prompt actually REACH the model?")
    print("Measured from prompt_tokens, not from the reply text.")
    print("=" * 72)
    print("Testing 'openai' placement only. 'anthropic' placement (top-level")
    print("'system') is already ruled out by measurement: a live run sent the")
    print("same user message bare and then with a ~13-token top-level 'system'")
    print("key, and prompt_tokens was 8 both times -- the text was never billed")
    print("as input, so the proxy dropped it before the model saw it. Re-testing")
    print("a question already answered would just spend a call.")

    base = base_payload(CANARY_MAX_TOKENS)
    if send_model:
        base["model"] = MODEL_NAME

    openai_payload = dict(base)
    openai_payload["messages"] = ([{"role": "system", "content": CANARY_SYSTEM}]
                                  + minimal_messages())
    r3 = send(openai_payload, "system in messages (openai)")
    status3, err3, content3 = r3["status"], r3["error_type"], r3["content"]
    ok3 = status3 == 200 and err3 is None

    if err3 in FATAL:
        print(f"\nTERMINAL: {err3}. Stopping.")
        return 1
    if status3 is None:
        print("\nTERMINAL: network error/timeout on the canary call. Nothing resolved.")
        return 1
    if status3 == 200 and err3:
        print(f"\nTERMINAL: HTTP 200 but the body did not parse ({err3}). Not a")
        print("verdict on system placement -- check the body above.")
        return 1
    if status3 == 429 or err3 == "server_error":
        print(f"\nTERMINAL: {err3} (status {status3}) -- transient, not a placement")
        print("verdict. Re-run later; free in dev mode.")
        return 1

    message_format = None
    unresolved_reason = None

    # PRIMARY EVIDENCE: prompt_tokens delta against STEP 1's bare baseline.
    #
    # This replaces canary-word matching as the deciding signal, and the reason
    # is what a live run showed: the reply can stop early for ordinary reasons
    # (a small max_tokens), which makes "is the magic word present?" unreliable
    # while saying nothing about whether the prompt was delivered. The input
    # side has no such problem. If the system text was part of the prompt it is
    # billed as input; if the proxy dropped it, it is not. Nothing that happens
    # to the output can change that.
    delivered = None
    if baseline_prompt_tokens is not None and r3["prompt_tokens"] is not None:
        delta = r3["prompt_tokens"] - baseline_prompt_tokens
        delivered = delta >= SYSTEM_DELIVERY_MIN_DELTA
        print(f"\n   prompt_tokens: {baseline_prompt_tokens} bare "
              f"-> {r3['prompt_tokens']} with system  (delta {delta:+d}, "
              f"need >= {SYSTEM_DELIVERY_MIN_DELTA})")

    obeyed = bool(content3 and CANARY in content3.upper())

    if delivered is True:
        message_format = "openai"
        print(f"\n=> RESOLVED: system-in-messages IS DELIVERED -- the system text is "
              f"billed as input, so the model receives it.")
        if obeyed:
            print(f"   The model also OBEYED it ({CANARY} echoed back), so the "
                  f"instruction is being honoured as a system prompt.")
        elif r3["hit_cap"]:
            print(f"   Obedience unconfirmed: the reply hit the {CANARY_MAX_TOKENS}-token")
            print( "   cap before the canary appeared. Delivery is what matters for the")
            print( "   pipeline and is established above, so this is not a blocker.")
        else:
            print( "   Obedience NOT confirmed: the text was delivered but the model did")
            print( "   not follow it, which can mean the proxy forwards a 'system' role")
            print( "   as an ordinary conversation turn. The rules still reach the model,")
            print( "   so this is usable -- but expect weaker instruction-following than a")
            print( "   true system prompt, and treat SYSTEM_PROMPT adherence as a thing to")
            print( "   verify in the demo rather than assume.")
    elif delivered is False:
        print( "\n   prompt_tokens did not move, so system-in-messages looks dropped")
        print( "   too -- the top-level form already was. Going to STEP 4 rather than")
        print( "   concluding, because that verdict rests on prompt_tokens being a")
        print( "   faithful input counter, and that has not been established.")

        print()
        print("=" * 72)
        print("STEP 4 -- instructions inside the USER message ('prepend'), which")
        print("also VALIDATES prompt_tokens as a measuring instrument.")
        print("=" * 72)
        print("Two questions, one call. If prompt_tokens rises here, the counter")
        print("responds to input size -- which retroactively confirms STEP 3's")
        print("delta of 0 was a real drop, not a broken metric. If it stays at")
        print(f"{baseline_prompt_tokens}, then prompt_tokens is NOT measuring input on this")
        print("endpoint and every delta so far was uninformative; the canary in the")
        print("reply becomes the only usable evidence.")

        # Mirrors exactly what api_client._prepend_system() produces, so a pass
        # here is a pass for the real pipeline and not for a probe-only shape.
        prepend_payload = base_payload(CANARY_MAX_TOKENS)
        prepend_payload["messages"] = [{
            "role": "user",
            "content": f"{CANARY_SYSTEM}\n\n{minimal_messages()[0]['content']}",
        }]
        r4 = send(prepend_payload, "instructions in user message (prepend)")
        status4, err4, content4 = r4["status"], r4["error_type"], r4["content"]
        ok4 = status4 == 200 and err4 is None

        if err4 in FATAL:
            print(f"\nTERMINAL: {err4}. Stopping.")
            return 1

        obeyed4 = bool(content4 and CANARY in content4.upper())
        delta4 = None
        if baseline_prompt_tokens is not None and r4["prompt_tokens"] is not None:
            delta4 = r4["prompt_tokens"] - baseline_prompt_tokens
            print(f"\n   prompt_tokens: {baseline_prompt_tokens} bare "
                  f"-> {r4['prompt_tokens']} with instructions in the user message  "
                  f"(delta {delta4:+d})")

        instrument_ok = delta4 is not None and delta4 >= SYSTEM_DELIVERY_MIN_DELTA

        if instrument_ok and obeyed4:
            message_format = "prepend"
            print( "\n=> RESOLVED: 'prepend' DELIVERS and the model OBEYS.")
            print( "   prompt_tokens rose here but not in STEP 3, which validates the")
            print( "   counter AND confirms both separate placements really are dropped.")
            print(f"   The model echoed {CANARY}, so the rules are being followed.")
        elif instrument_ok and not obeyed4:
            message_format = "prepend"
            print( "\n=> RESOLVED WITH A CAVEAT: 'prepend' delivers (prompt_tokens rose),")
            print( "   but the model did not echo the canary. The text arrives; adherence")
            print( "   is unproven. Treat instruction-following as something the demo has")
            print( "   to demonstrate, not assume -- reasoning.py's verification suite is")
            print( "   the backstop for exactly this.")
        elif obeyed4:
            message_format = "prepend"
            print( "\n=> RESOLVED, but prompt_tokens IS NOT A USABLE INSTRUMENT on this")
            print(f"   endpoint -- it stayed at {baseline_prompt_tokens} even with a longer user")
            print( "   message. So every delta measured above was uninformative, and")
            print( "   STEP 3's verdict should NOT be read as proof the other placements")
            print( "   are dropped. What IS proven: the model echoed the canary here, so")
            print( "   'prepend' reaches it. Use prepend because it is demonstrated, not")
            print( "   because the alternatives were disproven.")
        else:
            unresolved_reason = "nothing_delivers"
            print( "\n=> UNRESOLVED, AND THIS IS THE BAD OUTCOME: no placement is")
            print( "   demonstrably delivered -- not even text inside the user message,")
            print( "   which the model must be able to see for the endpoint to work at")
            print( "   all. prompt_tokens did not move and the canary did not come back.")
            print( "   That points at something more fundamental than placement: the")
            print( "   proxy may be substituting its own prompt, or ignoring message")
            print( "   content entirely. Inspect the replies printed above before")
            print( "   spending real budget.")
    elif ok3 and obeyed:
        # No usable token counts, but the model echoed the canary -- that alone
        # proves the text arrived, since it could not repeat what it never saw.
        message_format = "openai"
        print(f"\n=> RESOLVED (on the canary alone): prompt_tokens was unavailable, "
              f"but the model echoed {CANARY}, which it could not do without having "
              f"received the instruction.")
    else:
        unresolved_reason = "no_evidence"
        print( "\n=> UNRESOLVED: no usable prompt_tokens in the response AND no canary")
        print( "   in the reply, so there is no evidence either way. Check the usage")
        print( "   block printed above for the field names this endpoint uses.")

    print()
    print("=" * 72)
    print("RESULT")
    print("=" * 72)
    total = 0
    for u in _billed_calls:
        total += (u.get("total_tokens")
                  or (u.get("prompt_tokens") or u.get("input_tokens") or 0)
                  + (u.get("completion_tokens") or u.get("output_tokens") or 0))
    print(f"Billed calls: {len(_billed_calls)}   Tokens spent: ~{total}")
    print()

    if message_format and send_model is not None:
        print("Paste these into .env:")
        print(f"    CORTEX_MESSAGE_FORMAT={message_format}")
        print(f"    CORTEX_SEND_MODEL={'1' if send_model else '0'}")
        if send_model:
            print(f"    CORTEX_MODEL={MODEL_NAME}")
        print()
        print("Then confirm the budget_remaining units printed above against")
        print("interpret_budget_remaining() in src/api_client.py before a full run.")
        return 0

    if unresolved_reason == "nothing_delivers":
        print("Schema NOT resolved: NO placement is demonstrably delivered, not even")
        print("text inside the user message. This is a blocker and it is not a tuning")
        print("issue -- inspect the replies above. Do not spend real budget until the")
        print("rules provably arrive.")
        return 1

    if unresolved_reason == "no_evidence":
        print("Schema NOT resolved: the response carried no usable prompt_tokens and")
        print("the canary did not appear, so neither signal was available. Check the")
        print("usage field names printed above and adjust send()'s prompt_tokens")
        print("extraction if this endpoint names them differently.")
        return 1

    print("Schema NOT fully resolved -- see the messages above. Do not run the")
    print("pipeline against real budget until it is.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
