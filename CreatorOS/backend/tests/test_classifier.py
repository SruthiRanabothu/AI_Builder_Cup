"""Classifier accuracy test (Phase D gate: >= 90% on 20-message set).

Run:  python -m pytest tests -v
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.classifier import classify, BUSINESS, SPAM, FAN_LOVE  # noqa: E402

# 20 curated test messages: expected bucket -> (message)
TEST_SET = [
    (FAN_LOVE, "I love your content, you're so inspiring!"),
    (FAN_LOVE, "Big fan, keep up the great work!"),
    (FAN_LOVE, "Hey! How are you? Love your recent reel."),
    (FAN_LOVE, "Your videos are so good, you're my favorite creator."),
    (FAN_LOVE, "Just wanted to say hi and that I really enjoy your page."),
    (SPAM, "Buy 10k followers instantly, click the link now!"),
    (SPAM, "You've won a lottery! Claim your prize here: bit.ly/xyz"),
    (SPAM, "Get rich fast with crypto, no risk, DM me now."),
    (SPAM, "Earn $500 a day working from home, sign up today."),
    (SPAM, "Free verified badge for your account, message now."),
    (BUSINESS, "Hi! We're Glow Skincare and we'd love to sponsor a reel. Budget is $1200."),
    (BUSINESS, "We saw your content and want a paid partnership. What are your rates?"),
    (BUSINESS, "Hello, this is Nordic Fit Apparel. Can we discuss a collab? We'll pay $800."),
    (BUSINESS, "We'd like to feature your products in a campaign. What's your budget for a sponsored post?"),
    (BUSINESS, "Are you open to brand deals? Our marketing team wants to work with you."),
    (BUSINESS, "Hi Maya, we're a tech brand offering $900 for a 3-post bundle. Interested?"),
    (BUSINESS, "We're planning an influencer campaign and you fit perfectly. Free product + payment."),
    (BUSINESS, "Can you promote our product on your channel? We offer compensation."),
    (SPAM, "Congratulations! You are our lucky winner. Send your details to claim."),
    (FAN_LOVE, "Thanks for sharing your journey, it really motivates me."),
]


def test_classifier_accuracy():
    correct = 0
    failures = []
    for expected, msg in TEST_SET:
        got = classify(msg)
        if got == expected:
            correct += 1
        else:
            failures.append((expected, got, msg))

    total = len(TEST_SET)
    accuracy = correct / total
    print(f"\nAccuracy: {correct}/{total} = {accuracy:.0%}")
    for expected, got, msg in failures:
        print(f"  MISMATCH expected={expected} got={got} :: {msg}")

    assert accuracy >= 0.90, f"Accuracy {accuracy:.0%} below 90% gate"


def test_classify_returns_valid_bucket():
    for msg in ["hi", "", "   ", "random text"]:
        assert classify(msg) in {FAN_LOVE, SPAM, BUSINESS}
