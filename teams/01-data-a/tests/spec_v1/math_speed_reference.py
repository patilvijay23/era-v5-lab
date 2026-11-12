"""Frozen speed reference: DA-C1-001 as it was before its speed-up (clean.py 11da63a27cca, specv1.md medicine 55).

Keep this body unchanged while testing that the faster rule gives the same result. Copied verbatim from the old clean.py.
"""
import re


def c1_reference():
    """The old medicine_c1 and its three regexes. Returns the namespace so tests can reach C1_LINE and C1_SITE."""
    # a whole line that is generic site chrome
    C1_LINE = re.compile(
        r"(?i)\s*(?:More Similar Questions|Similar Questions|Related (?:Questions|Posts|Articles)|Share (?:this|on \w+)|"
        r"Sign ?up|Log ?in|Subscribe|Cookie|Accept (?:all )?cookies|Privacy Policy|Terms of (?:Use|Service)|"
        r"All rights reserved|\u00a9.*|&copy;.*|Follow us|Skip to (?:main )?content|Show Tags|Replies|Views|"
        r"Contact - Home.*|Report (?:abuse|post)|Upvote|Downvote|Like this:|Loading\.\.\.|Previous Post|Next Post|"
        r"Recommended|Back to top|Quick Reply|Click here.*|Leave a (?:Reply|Comment)|Your email address will not be published.*|"
        r"Posted by.*|Tags?:.*|Categories?:.*|Hide Tags|Join (?:now|us)|Download (?:the )?App.*|Course Hero.*)\s*")
    # site chrome seen in this pack (forums, homework sites, document hosts, OEIS, GMAT Club ...); only on lines <= 120 chars
    C1_SITE = re.compile(
        r"(?i)Check GMAT Club Decision Tracker|It is currently \d+ \w+ \d{4}|GMAT Club Daily Prep|Display posts from previous|"
        r"GMAT\u00ae test is a registered trademark|\[#permalink\]|Kudos \[\?\]|This preview shows page|Sign up to view the full|"
        r"View Full Document|Ask a homework question|intentionally blurred sections|My Personal Notes arrow_drop_up|"
        r"^Open in App$|^Last Updated :|All times are GMT|The time now is \d{1,2}:\d{2}|Privacy Statement|"
        r"Remember Me\? Password|having trouble loading external resources|analy[sz]e our traffic|Want to see this answer and more|"
        r"^See Solution$|^Subscribe now$|Upcoming SlideShare|Are you sure you want to|Report Content as Inappropriate|"
        r"Open this post in threaded view|^Loading content$|The OEIS Community \| Maintained by|supported by donations|"
        r"You are Here: Home|Registered Office:|CYBER MONDAY|^Wiki User$|^Buscar$|^Uncategorized$|Created with Sketch|"
        r"best freelance writing portal|Comment sent successfully|Choose the classification system|Read More \u00bb|"
        r"TUTORIALS HOME|Top of Page|Our sister site|Everything was clear\?|Hello Guest!|Free\s+Algebra Tutorials!|"
        r"Teach yourself statistics|^Home >>|\u200e > \u200e|claim an answer you\u2019ll have 24 hours|Search Our Content Library|"
        r"filtered results|^Sort by$|tutors are online|snackBarMessage|Go To Main Page|^Show/hide solution$|"
        r"Correct! Wrong!|Tutorial is loading|^Filed Under:|^Exam Prep:|^Asked in:|Verified Answer \| Published|"
        r"^Guided Lessons$|^Course Content$|Doorsteptutor|Mark Forums Read|^Recommended$|DocShare\.tips|^Hide$|"
        r"Not now$|Write an Interview Experience|Your message has been successfully submitted|has the best spam protection|"
        r"posting guide http|Questions are from the workbook|^Share$|^Children$|Go back to editing|try BYJU|We\u2018ve got your back")
    # phpBB "Replies / <n> / Views / <n>" block, one value per line
    C1_REPLIES = re.compile(r"(?m)^Replies\n\d+\nViews\n[\d.]+K?\n?")

    def medicine_c1(text):
        keep = [l for l in text.split("\n")
                if not (C1_LINE.fullmatch(l) or (C1_SITE.search(l) and len(l) <= 120))]
        return C1_REPLIES.sub("", "\n".join(keep))

    return {"medicine_c1": medicine_c1, "C1_LINE": C1_LINE, "C1_SITE": C1_SITE, "C1_REPLIES": C1_REPLIES}
