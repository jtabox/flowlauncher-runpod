### SUCH A SILLY FLOWLAUNCHER PLUGIN

**Feat. Why Did I Spend Half My Sunday On It & Other Thoughts I Guess**

Here's Copilot rapidly autocompleting his autocompletions and not allowing me to think what to write:

> *When I rent a cloud GPU at runpod.io, I always stress myself to check my balance so it doesn't run out and my storage volume is released back to the aether. I'm not sure why I'm so paranoid about it, but I am. I'm also not sure why I'm so lazy about it, but I am. So I thought, "Hey, why not make a Flowlauncher plugin that checks my balance for me?" And so I did. And it was silly. And I spent half my Sunday on it. And I'm not sure why I'm*

I stopped him there.


---

But yeah, it's a plugin for FlowLauncher that checks balance and current spending rate at runpod.io and calculates how much time is available, when exactly the balance is going to be depleted etc.

Requires [creating an API key at runpod.io](https://docs.runpod.io/get-started/api-keys) in order to access their [GraphQL API](https://graphql-spec.runpod.io/), and setting that key as an environment variable named `RUNPOD_API_KEY`.

Check `requirements.txt` for information on dependencies and what to do with them.

---
