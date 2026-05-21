# Keith Woods — Discovery Checkpoint

- **Date:** 2026-05-21 14:01 UTC
- **Duration:** 56 min
- **Attendees:** Brad Wilcox (AAA), Keith Woods (AU Group)
- **Fireflies ID:** `01KS5DEHCPMNR6TWA5QQZ2D8SV`
- **Meeting link:** https://meet.google.com/ayr-sqcd-shh

## Topic

Locked the open scope + access decisions before build begins — target states, exclusions, claim-amount floor, contact-selection rules, and the credentials/data handoff list. Driven from an HTML deck of Yanji's open questions.

## Source

Pulled via Fireflies MCP. See ID above for the canonical record.

---

## Transcript

```
Id: 01KS5DEHCPMNR6TWA5QQZ2D8SV
DateString: 2026-05-21T14:01:14.000Z
Privacy: link
Speakers: Brad Wilcox, Keith
Sentences: Brad Wilcox: Keith, man.
Brad Wilcox: Hey, dude.
Brad Wilcox: Long time no see.
Keith: How you doing?
Brad Wilcox: All right.
Brad Wilcox: Oh, where.
Keith: What?
Brad Wilcox: PGA track is that a minute?
Keith: Hold on one second.
Keith: I cannot hear you.
Brad Wilcox: Can you hear me?
Brad Wilcox: How about now?
Brad Wilcox: Is it me?
Keith: Okay.
Keith: Kind of working now.
Brad Wilcox: Kinda.
Brad Wilcox: Okay.
Keith: Okay.
Keith: Yeah, no, I can hear you now.
Keith: I have a. Yeah, I remember.
Keith: Different headset plugged in, and sometimes it'll.
Keith: It'll connect to that.
Brad Wilcox: So it happened last time I was talking to you.
Brad Wilcox: Good to see you, man.
Brad Wilcox: Good to be with you.
Keith: You too.
Keith: Yeah, I just want to run through.
Keith: I was looking at all that stuff, and I was like, I am not.
Brad Wilcox: I'm sorry.
Keith: Stuff is.
Keith: No, that's fine.
Brad Wilcox: I made it into a presentation to make it easy for us.
Brad Wilcox: So here we.
Brad Wilcox: Here we go.
Brad Wilcox: And I'm just recording the meeting with Firefly so that I have all this, because you can just answer and then we can get out of here.
Brad Wilcox: And everything's going smooth anyway.
Brad Wilcox: It's maybe going to be another week or two.
Brad Wilcox: But this is more for the deployment side because I got all of this stuff already on my side to do the development.
Brad Wilcox: But obviously we need to eventually hook up your accounts.
Brad Wilcox: So that's what this is about.
Keith: That's assuming that at some point you're going to need access to Zoom and everything.
Brad Wilcox: Salesforce.
Brad Wilcox: Yeah.
Brad Wilcox: So check it out.
Brad Wilcox: So here.
Brad Wilcox: Just, you know, what states do we want to monitor first?
Brad Wilcox: And it's okay if.
Brad Wilcox: If it's a lot of them, but what do you think the ask is if you had to pick five that are your top ones?
Brad Wilcox: You know, is it California, New York, Florida, or.
Keith: Well, I mean, we would want to do all of them.
Keith: Just because where the bankrupt company is doesn't necessarily.
Keith: Yeah.
Keith: Somewhat of an indicator of where the impact of companies are going to be, but it would be.
Keith: Ideally, we want to do everybody because it could be a company in California, you know, selling to, you know, companies in New York, Pennsylvania.
Keith: So we want to have all of them.
Brad Wilcox: I agree.
Brad Wilcox: And we'll get all of them.
Brad Wilcox: But to, like, refine, like, we're going to build something, and then you'll give some feedback on it, and you and I will probably just take some notes and then change this.
Brad Wilcox: This, and then we'll get you all of them.
Brad Wilcox: Cool.
Keith: Okay, so start with New York, New Jersey, Pennsylvania.
Brad Wilcox: Okay.
Keith: Florida and Michigan.
Brad Wilcox: Perfect.
Brad Wilcox: Florida and Michigan.
Brad Wilcox: Okay, cool.
Brad Wilcox: Gotcha.
Brad Wilcox: All right, that's one.
Brad Wilcox: That's easy.
Brad Wilcox: And number two, is there anything to, you know, the sales team, anyone besides yourself that you want involved at this?
Keith: I mean, eventually, you know, Some of these are going to be going out.
Keith: We're having.
Keith: We have to figure that out on our end of the.
Keith: Do we want these.
Keith: Having it set up where the emails.
Keith: I apologize.
Keith: I got Invisalign today, and all I can hear is like, I have a list all of a sudden.
Keith: And it's true.
Brad Wilcox: Don't crack yourself up too much.
Brad Wilcox: Keep.
Keith: I'm losing myself talking.
Keith: Oh, my God, it'll be gone in two days.
Keith: I'm like, okay, it better be, because I might just deal with crooked teeth rather than having to listen for the next six months.
Brad Wilcox: Oh, you had the shot.
Brad Wilcox: The shot.
Brad Wilcox: Like, your tongue feels like it's like a camel tongue hanging.
Keith: Yeah, it feels fine in there.
Keith: But I'm like, talking.
Keith: I'm like, okay, why am I not talking?
Keith: Right.
Keith: So, yeah, we have to figure out how we.
Brad Wilcox: Yeah.
Keith: Want to have that set up is like, do we just make, like, a dummy marketing account that, like, all the emails will come out of?
Keith: Do we want.
Keith: How do we.
Keith: Like, we got to figure that out.
Brad Wilcox: So usually.
Brad Wilcox: Yes, usually, absolutely.
Brad Wilcox: Have it come out of.
Brad Wilcox: Have it come out of an email.
Brad Wilcox: But who does it send the email to?
Brad Wilcox: And then if there's anything moving in Salesforce that needs to be assigned.
Brad Wilcox: Do you just want it one person?
Keith: For now, for me, it.
Keith: For right now, it's just going to be me.
Brad Wilcox: Okay, that's what I thought you're going to say.
Brad Wilcox: But later we can.
Brad Wilcox: We can add it.
Brad Wilcox: I mean, if you love this.
Keith: Ideally, eventually, if everything is working right now, I'm the only one using Salesforce, I want to bring in our other guys to use it as well.
Keith: So then ideally, based on where the account is or just go, oh, this account's in Michigan.
Keith: So it goes to Mike, you know.
Brad Wilcox: Yeah.
Brad Wilcox: It'll know automatically based on his territory.
Keith: Yeah.
Brad Wilcox: Okay, that's fair.
Brad Wilcox: All right, cool.
Brad Wilcox: So we're already on three.
Brad Wilcox: So this one is for you.
Brad Wilcox: This is kind of nuanced since you set up this whole flow.
Brad Wilcox: You know, if you don't mind just talking me through this again.
Brad Wilcox: And I know we've had a lot of conversations about it, but what counts as a real lead, because there's good leads, there's bad leads, there's big ones.
Brad Wilcox: We're going to talk about some of the public leads that are on there, and I wasn't sure about that.
Keith: Yeah, I mean, ideally, we want it to be.
Keith: I'm just pulling one open right now just to, like, look at a typical one.
Keith: Ideally, we want to.
Keith: Sometimes they're going to have banks on there, you know, lenders which are not relevant to us.
Keith: We don't need those.
Keith: So it's really, you know, if there's individuals on there, we don't need those.
Keith: I would probably also say we can like build in a, a dollar amount.
Keith: Sometimes you'll have them on there where there's, there's a bunch of names but they're just very small amounts where.
Keith: Right, okay.
Keith: It doesn't matter.
Keith: We don't need to do an entry and send an email.
Keith: For a company that is owed $1,200.
Brad Wilcox: What's your floor then?
Keith: I would say 10.
Keith: 10,000.
Brad Wilcox: Okay, cool.
Keith: And like I don't know if there's a like that 10,000.
Keith: It only it kind of also does depend on like let's say that 10,000 is to a massive public company.
Keith: It's not really, I don't know how fine tuned that can get over time of like yeah, a, a mid size, you know, no one's going to be, you know, with those smaller ones.
Keith: It's a different message because it's like we know that number is not going to, you know, be a problem for them.
Keith: It's more just like, hey, obviously maybe this is front brain for you.
Keith: You know, curious if you want to talk about what may happen with a larger balance.
Keith: You know, like a little bit of a wake up call, you know, 10 would be the minimum.
Keith: I don't know if there's any way to customize that further of 10's the minimum.
Keith: But like if it ends up being a company in Zoom that says they do a billion dollars in sales, it's like no we don't.
Brad Wilcox: Yeah.
Keith: Again if that starts getting like too,.
Brad Wilcox: It's too detailed, like crowded.
Brad Wilcox: Right.
Brad Wilcox: It's too big of a, too small.
Keith: It just doesn't make sense.
Keith: Like they're not gonna, you know, for companies of that size, like it's going to be a really, really big loss for it to really register to them.
Keith: But like if it's a company doing 10 million bucks and they're like yeah, we didn't see that one coming.
Keith: It's obviously the hit's not going to hurt us.
Keith: But yeah, we do.
Keith: If that happened with some other customers, it could have been a big problem.
Keith: So you know, we're open to hearing about it.
Keith: You know, if we just want to start simple, you know, we could just say 10,000.
Keith: Then like down the road we can figure out if there's ways to or just yeah build in of like,.
Brad Wilcox: You.
Keith: Know, we still want that Info, I guess to go in.
Keith: But maybe say if it's, you know, it's under this dollar amount.
Keith: For a company with sales that exceed this dollar amount, there is no, no email is triggered or something.
Brad Wilcox: That's cool.
Brad Wilcox: So how about.
Brad Wilcox: So for now we'll just do that one logic.
Brad Wilcox: But during a week or two after you get your hands on this, you can just be giving, you know, conditional logic statements and say, hey, add this, at this, at this and I'll fine tune it for you because I know you have to pay.
Brad Wilcox: That's the thing.
Brad Wilcox: It's not like you really want the, the fire hose.
Brad Wilcox: Right.
Brad Wilcox: Because it's going to cost too much.
Brad Wilcox: And so we should put a ceiling and a floor and.
Keith: Well, it doesn't cost us anything for.
Keith: No, if we have to buy, you know, like we said, if it's not the initial list, if it's the list that we have to buy.
Keith: Yes, then there is a cost there.
Keith: But like, if this goes into.
Keith: It pulls the top 20 and, you know, it sends out 17 emails compared to 10 emails like that.
Keith: That is.
Keith: No, there's no cost associated with that.
Brad Wilcox: Okay, cool.
Brad Wilcox: All right then.
Brad Wilcox: So let's get as many as we can for now.
Brad Wilcox: So we just went over this.
Brad Wilcox: It's just the inverse of the last question.
Keith: Yeah.
Keith: And I'm trying to think of, like, ones to avoid.
Keith: I mean, I could probably give you like, keywords.
Keith: Yeah.
Keith: You know, usually anything with finance in the title, insurance in the title.
Brad Wilcox: Okay.
Keith: You know, an LLP kind of indicating like a law firm.
Brad Wilcox: Okay.
Brad Wilcox: That would be whatever.
Keith: Capital.
Keith: What?
Keith: You know, there's a.
Keith: There's definitely.
Keith: I could come up with like, I could just come up with a bunch of keywords, you know, and I could just also then throw in the names of like a lot of the lenders that we commonly see in there.
Keith: Because again, if it's not perfect and maybe by doing that it excludes like one here or there that like, ideally would have liked to include.
Keith: That's fine.
Keith: But you know, there is just some of these lenders that are going to be on so many of them and we don't need to reach out to them.
Keith: Or I can just put.
Keith: I can create a list of keywords of, you know, these are the ones to avoid.
Brad Wilcox: Okay.
Brad Wilcox: And you just gave me a few conditions, so I'll make sure that what you just mentioned is included or excluded, I should say.
Keith: Yeah.
Brad Wilcox: All right.
Keith: Because then there's like, things we could use like one, you know, just like specific lenders that will often see I can't even think of who they are off the top of my head, but there's a bunch that will always continually see.
Keith: So, yeah, I could easily come up with a list of names and keywords that could just be avoided.
Brad Wilcox: Okay, perfect.
Brad Wilcox: That's great.
Brad Wilcox: All right, so that's that.
Brad Wilcox: So far, so good.
Brad Wilcox: And I know we're not in the complicated weeds yet, but we're getting there.
Brad Wilcox: So this one, You know, this is what we're going to use to, like, basically.
Brad Wilcox: Well, to test, we're going to use this.
Brad Wilcox: This data set.
Brad Wilcox: That's a really good thing to have, actually.
Brad Wilcox: And then I was wondering if you wanted.
Brad Wilcox: We talked about this when we spoke last time, when we put together the personalization.
Brad Wilcox: Do you want me to.
Brad Wilcox: To do something like how you've been pitching this?
Brad Wilcox: I've been hearing you say, you know, kind of your.
Brad Wilcox: Your lead in Icebreaker is, you know, you've appeared in 13 bankruptcies over five years.
Brad Wilcox: Just something a bit to that effect.
Keith: No, because we're going to have.
Keith: We have templates already set up.
Keith: Oh, okay.
Keith: Got it in Zooming.
Keith: So ideally, I think the way it would work is if it's a.
Keith: We have to kind of get all the data into Salesforce.
Keith: So if it's a entry where there's nothing else and it's kind of, maybe this is the first entry in, then it can trigger that automatic email.
Keith: I would have to come up with, like, the exact parameters, but it would be, you know, if there was another bankruptcy email that went out in a certain time frame, we would just want to have it flagged and that.
Keith: Because again, like I said, like, we don't want that same template going to them three times in three months.
Keith: We'd rather, you know, have that first one go out, but then for the second one, have the system just flagging and say, hey, you know, you figure out what you want to do with this one.
Keith: But, you know, this is the second bank.
Keith: And then like, oh, this is the third bankruptcy.
Keith: Because those are the ones that we would probably just write our own, you know, do some research and write, like a regular email not using a template.
Keith: Okay, got it.
Brad Wilcox: But you have the first follow up.
Brad Wilcox: You've got the initial, you've got the first follow up.
Keith: Yeah, we have all that built into Zoom info.
Brad Wilcox: Yes, got it.
Brad Wilcox: All right, I can help you through that.
Brad Wilcox: That's cool.
Brad Wilcox: Okay.
Brad Wilcox: I mean, this is the game changer to be able to.
Keith: Very, very last part, because that's like their system is changing the.
Keith: The mass emailing that's right now it's a.
Keith: So pulling all the info out of Zoom, that's not going to change.
Keith: But the emailing component, they're moving it from.
Keith: It's called Engage now they're moving.
Keith: It's called Sales Loft.
Keith: I don't know exactly.
Keith: Yeah, the same thing, but different.
Keith: That hasn't happened yet.
Keith: So I guess like we probably want to table that email part till the very end because I've been putting off of our transition from Engage to Salesloft.
Keith: So I guess we could work on all the other stuff first.
Brad Wilcox: Okay, got it.
Brad Wilcox: So if we can get it that far to where you're seeing.
Brad Wilcox: Okay.
Brad Wilcox: Did I already send it?
Keith: Okay.
Brad Wilcox: No, this is the first one.
Brad Wilcox: We'll just copy paste this template.
Brad Wilcox: Even that would be helpful at this point.
Keith: Yeah, because there's a. I mean.
Keith: If you want I could share my screen real quick.
Keith: I don't know if it would be help to.
Brad Wilcox: Yeah, let's check it out.
Brad Wilcox: Let me find you.
Brad Wilcox: There you are.
Keith: Unlocked.
Keith: Why won't this let me unlock my stupid password thing?
Brad Wilcox: Take your time.
Brad Wilcox: All right.
Keith: Is that sharing now?
Brad Wilcox: Yes.
Keith: All right.
Keith: Okay, so what will like basically like what we need.
Keith: So this company was sit for this bankruptcy.
Keith: So come in new bankruptcy, put in the name, the name, the amount, the date, Save it.
Keith: And then in the details.
Keith: This is the part where this is like the customization for the.
Keith: For the email that goes out.
Keith: I'll figure out how to best handle that.
Keith: It's like we have two different closings.
Keith: Like if it's a small loss, we just use this closing because that will like change with the.
Keith: How the email closing is.
Keith: That's the basic closing.
Keith: We just put the bankruptcy name in here.
Keith: This is basically the variables that feed into the email template.
Keith: We save it and then what I'll normally do is just use the Chrome,.
Brad Wilcox: Whatever this is called the browser extension.
Keith: Extension.
Brad Wilcox: But it's not working.
Keith: Of course it's not going to work.
Keith: And then basically here you just go click, click, you know, pick the two names, put them into the bankruptcy sales flow.
Keith: Like that's the process of once we of course, obviously it's not working now, but yeah, you show me, you know, because these are the things that like so let's say this one got hit by another bankruptcy tomorrow.
Keith: It would come in here and see.
Keith: All right, you know, there was recent activity with them, you know, so it still enter everything in but then basically somehow flag to us, you know, Lynn, electrics, whatever, you know, review them for whatever reason.
Keith: You know, put all that because like ideally what we want is right now, I don't always fill in all this info because it just takes.
Keith: It's very time consuming, you know, but we want to, because we want to be able to like anytime you go to any random account, right, we have a complete history here of like everything that they've been hit with.
Keith: And I have a list that I've, you know, it's in a spreadsheet and I need to figure out how to get it into here because again, what we want to eventually do is be able to run reports and be like, you know, show us accounts have been hit with multiple bankruptcies in the last, you know, we want to just work on getting all these different signals and then being able to kind of, you know, act on them.
Keith: But that is like the main thing would be like, so it's a brand new one.
Keith: The first thing would be new bankruptcy.
Keith: Fill in that info.
Keith: Come to the details.
Keith: If it's over a certain dollar amount, it's basic closing.
Keith: If it's under a certain dollar amount, it's the other closing.
Keith: The.
Keith: Depending on who this.
Keith: I don't know how we do that.
Keith: That's for the email signature.
Keith: You know, the bankrupt name.
Keith: I put the company, I do like an abbreviated version of the company name because I always feel like it's a very obvious tell.
Keith: It's a mass email.
Keith: If it's like I saw that International Business Systems Incorporated, you know, was hit by bankruptcy.
Keith: Like no one talks like that.
Keith: It's just like that's clearly auto generated.
Keith: So I just like put in an abbreviated version that's short.
Keith: I don't know if all, like if the system can do all that, but like that it can do it automatic.
Brad Wilcox: Yeah, we can, we can build in to do that.
Brad Wilcox: That's a good idea to just say make sure you always abbreviate the business and give it some examples of other business abbreviations.
Brad Wilcox: Is there an export in here that you can share?
Brad Wilcox: I don't know a few of these so that I know what, you know, variables to send your way.
Brad Wilcox: Okay.
Brad Wilcox: I think it's on the list.
Keith: Yeah.
Keith: I just need to figure out like for these, these are all coming from me.
Keith: So I just pick if it's someone up in New York.
Keith: Yeah, I just change it.
Keith: So it's like my New York address and email in signature.
Keith: If it's PA or south, I use the PA just looks a little bit more custom.
Keith: I don't know.
Brad Wilcox: You set this up, right?
Keith: Yeah, I'm just trying to think of like in the future if we have multiple.
Keith: Multiple.
Brad Wilcox: Well, if you.
Keith: That's where it's going to get complicated because like, yeah, we can know, we can refactor it.
Brad Wilcox: We can add them.
Brad Wilcox: We can.
Keith: Yeah.
Keith: No, what I'm thinking is though, there's not a way like just to attach like there's going to be one Engage account.
Keith: I've actually, I've meant to talk with him about that.
Keith: Of like, I don't think there's any easy way for it to be like, okay, switch to Keith's Engage account.
Keith: So now the email is coming from my.
Keith: Okay, this is from Mic.
Keith: So it's now coming from like.
Brad Wilcox: Right.
Keith: It would just be impossible.
Keith: That's why I'm thinking we might just make a.
Keith: A generic email that everything comes from.
Keith: But maybe we would still use these.
Keith: So if it's going to a Michigan company, we'll just have a Michigan thing in here.
Keith: So we'll pop in Mike's info.
Keith: So it's still coming from maybe like AU Marketing.
Keith: Or we'll just make it a person but make it look like it's a local person because that's like the whole thing is they don't want it to look that local.
Keith: But I don't think there is any for the cold.
Brad Wilcox: I see what you're saying.
Brad Wilcox: Like one agent.
Brad Wilcox: But it's got to be location specific in all of the regions.
Keith: Yeah.
Keith: Or maybe it's just one email.
Keith: Maybe like a generic email.
Keith: But like it could have signature.
Keith: Our signature.
Brad Wilcox: It's pretty tricky.
Brad Wilcox: But yeah, I get it.
Brad Wilcox: I get the problem you're trying to solve.
Brad Wilcox: So I know we can figure out a solution.
Brad Wilcox: Yeah.
Brad Wilcox: Okay.
Brad Wilcox: Two things.
Keith: I think it's easy enough.
Keith: We can just say like, okay, turn this to PA and PA will just put in my total email signature.
Keith: But it would still come from like a marketing at AU Group.
Keith: So that's what I just.
Keith: That's for me to figure out.
Brad Wilcox: Yeah.
Keith: Yeah.
Keith: I can send you a few examples.
Brad Wilcox: A few examples.
Brad Wilcox: And then secondly the schema from Salesforce.
Brad Wilcox: So we've got basically what you're entering in because you can see you're not putting everything.
Brad Wilcox: And you just said you want all the enrichment.
Brad Wilcox: That's what you're putting in.
Brad Wilcox: But the total schema, which are all the fields possible in this profile, not everything in, you know, the whole like kitchen sink of Salesforce.
Brad Wilcox: But whatever you're using that you would.
Keith: Like to use related to this.
Brad Wilcox: Related to this.
Brad Wilcox: So probably there's an export schema there.
Brad Wilcox: I can, I can Send you some documentation if it would be helpful.
Keith: Okay.
Keith: Everything I just showed you is pretty much because once it exports the company from Zoom, it populates all this other stuff.
Keith: So.
Brad Wilcox: Right.
Keith: The purposes.
Keith: Purposes of this, it would really just be the bankruptcy and then this stuff because everything else is going to be automatically done.
Brad Wilcox: Okay.
Brad Wilcox: So if you've got one that's automatically done and even a screenshot, and I'll build this schema.
Keith: Okay.
Brad Wilcox: Yeah, a couple of them.
Keith: Like maybe three.
Keith: Yeah.
Keith: Because when you push it over, all this is going to be done is automatically filled in from Salesforce.
Keith: I mean, from Zoom.
Keith: So the only thing we would be editing is like these.
Keith: Engage variables and the bankruptcy.
Brad Wilcox: Okay.
Brad Wilcox: All right.
Brad Wilcox: That's cool.
Brad Wilcox: Nice.
Brad Wilcox: All right, let me keep going.
Keith: Yeah.
Brad Wilcox: These are just little details here.
Brad Wilcox: Do you mind if I take back the control?
Brad Wilcox: So you probably saw these already.
Brad Wilcox: ABC Core versus ABC Corporation, this sort of thing.
Brad Wilcox: So at this stage, do we.
Brad Wilcox: How do we want to flag dupes?
Brad Wilcox: Do you want to review them yourself or do we just want to put in the logic and, you know, trust that it's fine?
Brad Wilcox: And then do you want a log that you would be able to check some CSV off to the site at the end of the month?
Keith: I guess.
Keith: How would this work?
Keith: Would it be.
Keith: Because, like, what I end up doing is with a new one.
Keith: If I'm not familiar with the name, I'll quickly search it in Salesforce just to see if it's already in there.
Brad Wilcox: Right.
Keith: If it's not, it does go to.
Keith: I'll go to Zoom.
Keith: And because I push everything through Zoom, it kind of.
Keith: Kind of avoids that from happening.
Keith: It'll find them because every name in Salesforce is the name that is set up in Zoom.
Keith: Okay.
Keith: So usually Zoom will catch.
Keith: If I put in ABC Corporate.
Keith: Mean, like, oh, you mean ABC Corporation, and then that's what will get pushed to.
Brad Wilcox: Then all we need is your Zoom API key and we'll do the same.
Brad Wilcox: We'll do the same exact thing.
Brad Wilcox: So you'll have.
Keith: Do I have a Zoom API key?
Brad Wilcox: You may have to ask them for it.
Brad Wilcox: But if you do, we can log in right now.
Brad Wilcox: If you want me to just follow every.
Brad Wilcox: If you don't mind, because I'll tell.
Keith: You pretty quick, I don't.
Keith: Is that something that is just like, normally included or is that something like separate you have to pay for.
Brad Wilcox: Normally it's included, but for enterprise software, sometimes it's the latter, unfortunately.
Brad Wilcox: So let's find out.
Brad Wilcox: You'll have a Salesforce one for sure.
Brad Wilcox: They're a little bit more lenient on it, but 95% of these platforms have one for free.
Brad Wilcox: So it's probably in something called Integrations.
Brad Wilcox: Maybe under your name in the profile on the top corner.
Brad Wilcox: Might be there in Settings.
Keith: Oh, Integrations.
Keith: Yeah.
Keith: That's under.
Brad Wilcox: Admin.
Keith: Yeah.
Brad Wilcox: Usually it's an admin thing.
Brad Wilcox: Okay, cool.
Brad Wilcox: Please be an API.
Brad Wilcox: Yep.
Brad Wilcox: Connections is good.
Brad Wilcox: CRM.
Keith: These are the ones that we just have.
Brad Wilcox: In there.
Brad Wilcox: Maybe the Integrations tab.
Brad Wilcox: Let's see if it's here.
Brad Wilcox: Okay, let me just.
Brad Wilcox: I was going to Google it, so it's.
Brad Wilcox: I know they have one.
Brad Wilcox: Yeah.
Brad Wilcox: It's just a matter of.
Brad Wilcox: You're right.
Keith: If we need to ask some data.
Brad Wilcox: Yeah, that could be.
Brad Wilcox: They don't call it API.
Brad Wilcox: Apparently connect the tools use every day could be this.
Brad Wilcox: This is kind of a user interface of an API.
Keith: What would this need to be getting.
Brad Wilcox: Connected to this would allow us to write in this.
Brad Wilcox: These two connectors that we're talking about.
Brad Wilcox: So this.
Brad Wilcox: This exact scenario.
Brad Wilcox: Right.
Brad Wilcox: It's like, do I create ABC Core or am I just checking if it's already created?
Brad Wilcox: So let's say it's what I think the easiest.
Keith: I'll just show you like really quickly of.
Keith: Let's say.
Keith: We'll just say Hellbender.
Keith: Let's say this is a company that.
Keith: Is it a bankruptcy report?
Keith: So I find it employees.
Brad Wilcox: Yeah.
Brad Wilcox: All this enrichment data, it's already got everything scraped from LinkedIn.
Keith: All right.
Keith: I want this guy.
Keith: These are the two people I want.
Keith: Export, Contact, Explore.
Keith: And now it's done.
Keith: Yeah.
Keith: Now it's just here.
Keith: So then it would just be doing that and then just adding that stuff in because, like, I don't.
Brad Wilcox: What else would you want to add over if that's assuming there was nothing?
Brad Wilcox: Only the top decision makers.
Keith: Yeah.
Keith: Because those are the people that are going to be getting the email.
Keith: So that.
Keith: That's really it.
Keith: Because then if it's one that's already existing now let's say whoever add this person.
Keith: I think.
Keith: Yeah.
Keith: It doesn't necessarily tell you.
Keith: All right, well, I'll just try.
Brad Wilcox: So one Contact was created in Salesforce and added to my records.
Brad Wilcox: It says.
Keith: So like I know this company is already in my Salesforce.
Keith: So if you went in there.
Brad Wilcox: And.
Keith: Just said, I want to add this guy.
Keith: Yeah.
Keith: So I'll just say existing Salesforce account found.
Keith: So that means it's already in there.
Keith: Or I guess.
Keith: Does it not say that?
Keith: Yeah, I guess.
Keith: Point being, it doesn't really matter if you know you just want to start here because whether they're in there or not, it doesn't do anything.
Keith: Like, it's not a bad thing.
Keith: It doesn't like make a duplicate entry or anything.
Keith: So yeah, either says there is one or there's no account.
Keith: So yeah, I mean, I think that's how I always do it because sometimes I would first go if I know it's in Salesforce to go right there again.
Keith: Sometimes the name as it's listed in the bankruptcy document is not.
Keith: It's like real name.
Keith: And then usually in Zoom I'll be able to find its real name.
Keith: So all the names in Salesforce, 95% of my entries in Salesforce were entered through Zoom.
Keith: So it's however they're set up in Zoom.
Brad Wilcox: So we definitely need the API then.
Brad Wilcox: Okay, I'm just going to look into it and I'll send you an email.
Brad Wilcox: Okay.
Brad Wilcox: And what we would do, if you.
Keith: Want to, when I'm not, I can send you my username and I don't know, I'll look it up.
Keith: I'd be sending my username and password.
Keith: If you literally just want to go mess around in there and look around and try to figure out, let's do.
Brad Wilcox: That, that's fine, I'll do that and I'll try to get the API as well and I'll look into it and then that would be all I need.
Brad Wilcox: But I see that it's listing by C suite first, so it's pretty easy.
Brad Wilcox: You could just almost say like take the top five decision makers and here's.
Keith: The easiest way to do it.
Keith: So these are all like the filters.
Keith: So top contacts is okay.
Keith: So usually this is the one that's like a little bit tricky of figuring out who the right contacts are because it does matter a little bit on the company size.
Keith: I could, I mean I could build like a, almost like a chart of like if it's from, you know, ranking them because like if it's a hundred million dollar company, yeah, we want to email the cfo.
Keith: If it's a billion dollar company, we don't want to email the cfo.
Keith: You know, we're not getting to him.
Keith: So, you know, all these companies will have the top contacts.
Keith: And I have like the admin contacts, which is typically like, you know, the CFO's controller, you know, the people, you know, whatever decision makers.
Keith: And then the admin level, I could definitely build like a kind of like, like this, you know, we're not, you know, one.
Keith: They're going to have a Million employees.
Keith: The other thing is also for like some of these companies, of just making sure is the person, you know, okay, this person is local.
Keith: Sometimes you'll see, oh, it's the cfo, but he's in, you know.
Keith: Yes.
Brad Wilcox: Like working remotely or something, even though the company is down the road.
Keith: Yeah, well, because sometimes these will be like, international companies where, you know, we have to find a local contact.
Keith: I mean, and again, there's very.
Keith: Just like, go like this.
Keith: And now just say, okay, only.
Keith: So it goes from 6,200.
Keith: Okay, so these are all U.S. employees.
Brad Wilcox: You can see.
Keith: I could figure that out.
Keith: Because it does.
Keith: There's a lot of accounts in here that are just going to have a million options.
Keith: And it's like figuring out which is the right one could be a little tricky, you know, because I'll, like, look for the right contact.
Keith: But then I don't even know what these stupid fire things mean.
Keith: It just means they're more likely to respond.
Keith: So maybe it's like, fine, I'll go to, you know, to him.
Keith: I can kind of make a little workflow of how to choose.
Keith: Yeah.
Brad Wilcox: If there's tiers, let's say you have at least two tiers.
Brad Wilcox: Right.
Brad Wilcox: And one is over a certain limit of employees, then a different org chart needs to happen for the logic.
Brad Wilcox: But under it it's just cfo.
Brad Wilcox: All the C suites just grab them.
Brad Wilcox: After that, though, it's more complicated if they're bigger.
Brad Wilcox: Right?
Keith: Yeah.
Keith: I'm actually even wondering of, like, on a daily basis how many of these we're really going to be getting.
Keith: Of like, if the system just found the company, entered all the bankruptcy info into Salesforce and then basically told us, like, here are the five top companies from yesterday, like, with this Zoom link or whatever, how it'd be done.
Keith: Because, like, in.
Brad Wilcox: Yeah.
Keith: You know, now you just come to it.
Keith: Here's like, how to get to Zoom.
Keith: Of if we came in and just said, okay, we'll.
Keith: We'll go through the employees.
Keith: Because, like, I do feel like that's a.
Keith: It's kind of a.
Keith: It's a nuanced thing of just.
Keith: I've tried to do it with other stuff of just like, okay, we'll pick this person or that person.
Keith: And it just.
Keith: There's too many, like, factors that kind of play of like, okay, well, that person, yes, they're the perfect.
Keith: They're the controller.
Keith: But when you look at their contact info, they have an international cell phone, so they're not local.
Keith: So I don't think we're getting.
Brad Wilcox: You can't automate that many.
Keith: Where if it just set up like, hey, Keith, Here are the 20 companies from yesterday, and I could just click on the links for those 20.
Keith: Okay.
Keith: All the info has already been populated into Salesforce, where all I need to do is go in.
Keith: Go to click on the link that takes me to their Zoom profile.
Keith: Go.
Keith: Okay, I want this contact this.
Keith: I'll just pick the three contacts and then take your template, push it in Salesforce, and then I initiate the emails.
Keith: Because that's, you know.
Keith: Yes.
Keith: It's not taking, you know, 100 of it away, but, like, I just feel like that's an aspect that'll be very hard to get.
Keith: Right.
Keith: And, you know, if we could eliminate all the heavy lifting, we just do that one little part like that might.
Brad Wilcox: That's a good start.
Brad Wilcox: Right?
Brad Wilcox: That might make sense then.
Keith: Yeah.
Keith: Then we can see if.
Keith: Then we're like, you know what?
Keith: That's just not working because we can't keep up with it.
Keith: Then maybe we can go back and say, all right, we do want to figure out how to trigger it automatically.
Keith: It's just.
Keith: It's very nuanced.
Keith: And, you know, it's getting that right contact is so important because if all the other stuff is done, then it's like, it's not that hard.
Brad Wilcox: Yeah, it's more fun.
Keith: What's the hard part is, like, going through all the.
Keith: From Zero documents.
Brad Wilcox: Yeah.
Keith: Copying and pasting, taking them, you know, finding it like.
Keith: Okay, if we can get 85% of that done.
Keith: Yeah.
Keith: We'd rather.
Keith: We're better off doing that last 15%.
Brad Wilcox: Yep.
Keith: Cool.
Brad Wilcox: Okay, I'm going to share again.
Brad Wilcox: Perfect.
Brad Wilcox: Thank you for explaining that.
Brad Wilcox: It helps a lot, and I think we did just arrive at a good mvp.
Brad Wilcox: Okay, here's another nuance.
Brad Wilcox: What if the claim amount is missing?
Brad Wilcox: Does that ever happen?
Keith: Yes.
Keith: Then forget it.
Brad Wilcox: Forget it.
Brad Wilcox: Drop, move on.
Brad Wilcox: Yeah.
Keith: Okay.
Keith: Because a lot of times they will.
Keith: Because if it's missing, then, yeah, we just skip it too, you know, because, like, what are we gonna do with it?
Keith: We don't even know it could be a dollar, could be nothing.
Keith: So we don't bother.
Brad Wilcox: Okay.
Brad Wilcox: Because there's enough.
Brad Wilcox: There's already enough blue ocean for you.
Brad Wilcox: Okay, so how about this one?
Keith: I guess this kind of goes away.
Keith: Yeah.
Brad Wilcox: This further down.
Brad Wilcox: Yep.
Keith: Yeah.
Brad Wilcox: Further down the pipe.
Keith: Because again, I feel like that's also going to be a really tricky thing to kind of manage of, you know.
Keith: Yeah.
Keith: Having us manage the emails, as long as it just, like, Alerts us and lets us know, here are the 20 from yesterday.
Keith: And then it just like, all we have to do is go in, click this goes away, click the contacts that we want to push, and then we go into Salesforce.
Keith: Then once we're in Salesforce, we can see all that info.
Keith: We can now see the size of the bankruptcy, you know, so you don't have to worry about, like, what happens.
Keith: We could even then pick the variables.
Keith: We can pick that stuff where all you have to populate in is the, like the abbreviated name.
Keith: Yeah, it takes out a lot of the kind of nuanced pieces and just, it's more getting like the.
Brad Wilcox: It's really gonna.
Brad Wilcox: It's gonna go even quicker.
Brad Wilcox: I'm glad we had this conversation and you just, you just came to that conclusion, so that's cool.
Brad Wilcox: And we can.
Brad Wilcox: I mean, we can see it.
Keith: Yeah.
Keith: Because it also then takes away that email aspect of, like, how do we do this with the email?
Keith: It's like, we don't have to worry about that now because, yeah, Mike is going to be going in and triggering those emails.
Keith: So it'll automatically come from this.
Keith: You don't have to worry about making a dummy account or what.
Keith: Whatever.
Keith: Yep.
Keith: Okay.
Brad Wilcox: I think this is pretty much the last piece.
Brad Wilcox: Could you remind me what your workflow looks like today to get from zero?
Brad Wilcox: So how do you go looking through again?
Brad Wilcox: Do you want to share screen?
Keith: Yep.
Keith: Am I sharing or are you sharing?
Brad Wilcox: I'm taking.
Brad Wilcox: Yeah, you share.
Brad Wilcox: I'll stop sharing.
Brad Wilcox: There you go.
Brad Wilcox: Yeah, this is actually the end.
Keith: All right, so this is the dashboard.
Keith: What I do pretty much every day, new case of bankruptcy.
Keith: And I just start going down the list.
Keith: Click the view petition, just scroll through.
Keith: Okay, that one has nothing.
Keith: You know, go to the next slide.
Brad Wilcox: Yep, got it.
Keith: Okay, now, like here, like, as you said, we pick certain capital, you know.
Keith: Well, you know, if we're not doing.
Keith: We're not doing the automatic emails and like some of these.
Keith: Maybe I would leave then.
Keith: But like, like something like county tax.
Keith: Yeah, like, we don't want that one.
Keith: You know, Liberty Funding source again, name of.
Keith: Almost certainly not going to be a, you know, a hit for us.
Keith: Same thing with this one.
Keith: Like, we.
Keith: We can work in what those, like, keywords are.
Keith: But then, and I don't know how, like, they'll always have these up top of them.
Keith: Sometimes when you scroll down, they actually have the full list down here.
Keith: I mean, that is the extent of the list.
Keith: It's hard because, like, it's not always labeled I mean, there's certain things like this is always the headline or what you're looking for.
Brad Wilcox: Yep.
Keith: But it's not always, like, in the same format, you know, then we come to this one.
Keith: Again, you know, Capital, not going to be one.
Keith: Wells Fargo, not going to be one.
Keith: Stripe Capital not going to be one.
Keith: This one very good one.
Keith: Okay, we want to have that one.
Keith: Insurance.
Keith: We don't want that one.
Keith: You know.
Keith: This one.
Keith: Yeah, we want that one.
Keith: Okay.
Keith: You know, so there's a name.
Keith: You know, take that.
Keith: No, it's not sharing it now.
Keith: But then we take that into Zoom, find it in Zoom.
Keith: Because now if we're not moving the accounts in zoom, I mean, the contacts, all you would do is it.
Keith: You would come into here.
Keith: I just go tab of the servicing.
Keith: No, it's not it.
Brad Wilcox: And Keith, if we blow up your Zoom info, you know, if this comes in and there's like thousands of these, because even just in one, you have like five.
Brad Wilcox: So if there's a hundred a day, is this gonna trick you into the next account tier?
Brad Wilcox: And that's not good, or.
Brad Wilcox: No, it's okay.
Keith: No, it's fine.
Keith: I mean, that's what we have it for.
Keith: You know, that's literally why we're having this conversation, because, like, more, there are probably 100 a day and we can't keep up with them.
Keith: So.
Brad Wilcox: Got it.
Keith: No, that is.
Brad Wilcox: That's a good level.
Brad Wilcox: Okay.
Keith: Yeah, we have tons of those, you know, and then it's the.
Keith: Yeah, some of these initial petitions will have the.
Keith: They always have, like, that top 20.
Keith: And then sometimes in that same initial position petition, they will have.
Keith: Just thought where to go here.
Keith: You know, the schedule it has.
Keith: Now, this has the full list, very short list, but it has the full list.
Keith: And sometimes this will be a separate document.
Keith: So that's like the hard thing to kind of.
Keith: I always start with the initial condition because that'll usually have the top 20.
Keith: But then it's like the figuring out of, like, how to.
Keith: It's like, let's say.
Keith: You can add any account to it.
Keith: Like when this one popped up, whenever it was, you click to add the dashboard.
Keith: I'll normally do that with ones where, you know, there's a handful of accounts where it's like, okay, that top 20 was pretty good.
Keith: I want to come find that full list whenever it's ready.
Brad Wilcox: Right.
Keith: This will updated as new accounts are or as new dockets are being updated.
Keith: So once a week, I come in here and I try to scroll through them to just See, like, okay, did the full list get released yet?
Brad Wilcox: You manage that separate right now.
Brad Wilcox: That's another workflow.
Keith: It's another thing that is not.
Keith: I have a very hard time staying on top of it.
Keith: Could be, you know, because it's.
Keith: There's not an easy way to do it.
Keith: You kind of have to like, scroll through and eyeball it.
Keith: There's a couple terms.
Keith: You can search, but eventually, you know,.
Brad Wilcox: It'll,.
Keith: You know, like, they'll pop up and then, you know, you can go through it and it's the full.
Keith: It's the full.
Keith: Let me.
Keith: I.
Keith: Just.
Keith: Moving so slow.
Keith: I'm just gonna think of one.
Keith: We did yesterday it.
Keith: Out of here.
Keith: So it's like you have the long list.
Keith: So there's that initial petition, but then up here again, it's hard to kind of.
Keith: You kind of have to like, read through them, but it's like, okay, that's it.
Keith: So then you pay to download it.
Keith: But now this is that full list.
Brad Wilcox: Right, right, right, right.
Brad Wilcox: Because the one we're looking at comes out quick when there's just the first.
Keith: That one comes out quick.
Keith: This is the one that comes out later on.
Brad Wilcox: Yeah.
Keith: So this would be the one that, like, we talked about trying to find a way where it can, like scan through to be like, hey, we think we found the schedule app and we can look at it and go, yes, bye.
Keith: And then basically do that exact same process we're doing with the other ones with this.
Keith: Because this is where this becomes very.
Brad Wilcox: It's a warmer.
Keith: Awesome, awesome prospects.
Keith: Very time consuming.
Keith: Right.
Keith: As we're also skipping over a ton of them.
Keith: Doing this takes couple hours because, like, yeah, okay, let's get this one.
Keith: You know, copy it, paste it into Zoom, you know, move all.
Keith: Like, if all we had to do was someone said, okay, there were 30 names in there for Mike.
Keith: Here are the 30 names and Mike just clicks on each one.
Keith: It takes it right to the Zoom page.
Brad Wilcox: Yeah.
Keith: And then he picks the contacts and then he initiates the email where he doesn't have to, you know, copy and paste from this list entered into Zoom, Take it from Zoom, push it into Salesforce, enter the bankruptcy info in Salesforce.
Keith: If all that's being done, where all he has to do is pick the contacts and then initiate the email we can get.
Keith: You know, that takes us from being a couple hours to get through to, you know, 15 minutes.
Keith: And he can be the one to judge of like, okay, I wanna.
Keith: I don't wanna send a generic email to this guy.
Keith: I Wanna do something separate.
Keith: But yeah, that's kind of the process of like, you know, this came out on in March so you know, this would have found it in March and then you know, the follow up came out in April, you know, so it's just keeping on top of them.
Keith: It's really hard.
Keith: So if there's a way to.
Keith: Anytime signal.
Brad Wilcox: Yeah.
Brad Wilcox: To get, you know.
Keith: Yeah.
Keith: And it would maybe be like if it's a.
Keith: Maybe it just puts all of them into the dashboard and then we can go through and kind of look at it because you know there's somewhere.
Keith: It's like we don't put them all into the dashboard to follow up on them.
Keith: It just kind of depends on like based on the size, based on, you know, okay, the initial list was really good.
Keith: So chances are the full list will be really good.
Keith: We want to keep that one in.
Keith: You know, the initial list is.
Keith: It's a handful of companies in California.
Keith: You know, most likely nothing's going to come.
Keith: Like we don't want to save that one.
Keith: And like figuring out how to.
Brad Wilcox: Yeah, but you need the data.
Brad Wilcox: Like you've been talking about the report.
Brad Wilcox: You need the data to be able to screen it.
Brad Wilcox: But quick and efficiently without digging the data and starting from, you know, because.
Keith: It would be if it like dumped every, every single company into the dashboard.
Keith: We're talking like yeah, 50 a day.
Keith: We'd never be able to go through it.
Keith: So maybe if we say, you know, cases that have a certain amount of name, like if from the, if from the top 20, if any names are extracted from the top 20, maybe we say then that goes to the dashboard and we can just go through the dashboard and I can just remove them where the system is just scrubbing whatever is in the dashboard.
Keith: But we can remove stuff from the dashboard.
Keith: So if we just scroll through it, we're like, yeah, this one.
Keith: That doesn't make sense to be in there.
Keith: Let's get rid of it.
Keith: This one.
Keith: I don't know what's the best way to do this?
Brad Wilcox: How do you like the idea of that dashboard being in front of Salesforce?
Brad Wilcox: So it's the first step and the dashboard is the catch all.
Brad Wilcox: And you can do what you just said, you know, hey, take away like anything public, take away insurance companies.
Brad Wilcox: And then it's like every day you're screening them down or if you don't get to it that day, it's whatever's there, you can just knock it off.
Brad Wilcox: And then you say push to Salesforce the other way around.
Keith: Well, I think the initial, it's like two parts.
Keith: It's like the initial.
Keith: You know, when these come out on a daily basis, there's gonna like those top 20 names come out immediately.
Keith: Like we want to get those like on a daily.
Brad Wilcox: You need that and you need that email to be hot in their, in their inbox.
Keith: Yeah.
Keith: And then it's because that speed.
Keith: And then like let we just say, all right, if it extracts more, you know, five or more names from a bankruptcy report, it gets pushed to the, to the dashboard.
Keith: And then the dashboard is constantly being monitored.
Keith: And we can just go in and look the dashboard and say, now take this one out, take this one out.
Keith: Just so it's not wasting its time going through looking for the next.
Keith: And then just like alerting us of like, okay, you know, the schedule, effort, diversified, wire popped up on the dashboard.
Keith: Scrub it.
Keith: We could say scrub it.
Keith: And then it does the exact same thing where finds all the names.
Brad Wilcox: Yep.
Keith: More info, enriched, more info, pushes all the bankruptcy info and then we just get the list of you go and pick the names and trigger the emails.
Brad Wilcox: Okay, so as long as you show me in Salesforce where that data is going.
Brad Wilcox: Exactly.
Brad Wilcox: The schema and then a couple of examples of a fully, you know, filled out lead.
Brad Wilcox: That's all I need.
Brad Wilcox: And then this too.
Brad Wilcox: I'm sending it to you here in the Google Meet and I can also email this to you.
Keith: But I thought would it be helpful if like I did a, like a screen recording of just like what that process looks like?
Brad Wilcox: I already know because you've, you've been kind enough to do this demo to me twice now.
Brad Wilcox: I understand it again, I did the first time, but you know, it's your domain, so.
Brad Wilcox: And I'm putting myself in your shoes because you do a lot of jumping through hoops to get to this stuff, right?
Keith: It's a lot of back and forth and copy it just.
Brad Wilcox: Yeah, it's like, and you know, just tedious.
Keith: And it's like some days you have time for it, some days you don't.
Keith: And it's like the day you don't might be like you just missed out on a bunch of good.
Keith: Yeah, I can't even imagine the amount of like opportunities we miss out on because we just can't keep up with it.
Brad Wilcox: It's such a good use case for automation too.
Brad Wilcox: So.
Keith: Yeah, all right, I can teach anyone how to do this.
Keith: Like, it's so simple.
Brad Wilcox: I've got it and I've already been working on it and all the stories are scoped and everything, and we're getting pretty close.
Brad Wilcox: The OCR is done, which was the hard part to get the data off the dock.
Brad Wilcox: But though, did you see this thing I just shared?
Brad Wilcox: I just sent a piece of the.
Brad Wilcox: It's inside the comments of Google Meet, but I'll email you as well.
Brad Wilcox: It's basically like the three password things that we need the credentials for Salesforce Zoom info.
Keith: I don't normally use Google Meets.
Keith: I don't even know where that would be.
Brad Wilcox: Okay, I'll email.
Keith: Is it down here?
Keith: If you could email it to me, that'd be great.
Brad Wilcox: I'll email it to you.
Brad Wilcox: Don't worry.
Brad Wilcox: All right.
Brad Wilcox: And I don't want to take up any more of your time, but if you are able to send that information to me as soon as possible, it'll unlock, you know, the next phase, because I'm kind of blocked on that point now.
Keith: Okay, yeah, yeah, cool.
Brad Wilcox: And I'll be in touch.
Keith: I can take care of that today.
Keith: Absolutely.
Brad Wilcox: Okay, I'll email you right now then.
Brad Wilcox: Thank you, Keith.
Keith: Awesome.
Keith: All right, Brad, thank you so much.
Keith: I appreciate it.
Brad Wilcox: I appreciate it, too.
Brad Wilcox: Thank you for your time and thanks for your patience.
Brad Wilcox: All right, talk to you soon.
Brad Wilcox: All right, buddy.
Keith: Absolutely.
Keith: Okay, bye.
Brad Wilcox: Bye.
Title: Project Alignment between Brad Wilcox and Keith Woods
Host Email: No host email
Organizer Email: brad@automationarchitecture.ai
Calendar Id: No calendar id
Fireflies Users: No fireflies users
Participants: woods@au-group.com
Date: 1779372000000
Transcript Url: https://app.fireflies.ai/view/01KS5DEHCPMNR6TWA5QQZ2D8SV
Audio Url: https://cdn.fireflies.ai/01KS5DEHCPMNR6TWA5QQZ2D8SV/audio.mp3?Expires=1779591527&Policy=eyJTdGF0ZW1lbnQiOlt7IlJlc291cmNlIjoiaHR0cHM6Ly9jZG4uZmlyZWZsaWVzLmFpLzAxS1M1REVIQ1BNTlI2VFdBNVFRWjJEOFNWL2F1ZGlvLm1wMyIsIkNvbmRpdGlvbiI6eyJEYXRlTGVzc1RoYW4iOnsiQVdTOkVwb2NoVGltZSI6MTc3OTU5MTUyN319fV19&Signature=To142xcrooIYjTtbqTnKVkDnRQD9OWBNDFp-RH9rR26mnALnzC44HeiESPRClENxgt4vFEYVnjcNaOk9gT~PG8lUEI~4nA22VilkQj28FSoyOFPad5vOPOulomJ1GfKuEUnPReuKT8wmbMuFkNKPNBhc6NaOFgEsQnn7hcBG8FX~B6Ro~uyXa7yF5dUaucTV560cJwNGBIk29KDTQa~mQWLiSWPylcQuJI6O3H1HGCOnMyCFmAqgvggovt0Gh3ktfq5bk12UTCd2MGpPijlMfed7AHAzX-6PXWWd1LJEmpnAdgiwzEUMTUAgAQYVYo3d1rdYwIQvBMLFD46Y3ZBhcA__&Key-Pair-Id=KSZO9HH55DSRO
Video Url: No video url
Duration: 56
Meeting Attendees: woods@au-group.com
Cal Id: No cal id
Calendar Type: No calendar type
Meeting Link: https://meet.google.com/ayr-sqcd-shh
Is Live: false
```
