# A.L.I.C.E. PROJECT

See whole documents at: [https://jeffliulab.github.io/ALICE_Document/](https://jeffliulab.github.io/ALICE_Document/)

This is an entertainment project, inspired by the following two:

* Stanford PhD Candidate Joon's Generative AI HCI research
* Alice and stress test settings in Underworld of Japanese anime Sword Art Online

The project's planned FEATURES are as follows:

* 2D version of Underworld
* Initial residents settings
* Players can sneak into the setting, and players can talk to residents to "pollute" residents' memories and impulses
* In the center of the map is a church, a top-down manager, managing the thinking of local residents; when the church finds someone has an idea that violates the rules (the discovery must be made by the church's police during interaction and patrol, and the church cannot directly scan other residents' minds)

The goals of the project are as follows:

* Stress test: 300 years later, monsters from the demon world will invade the town, and the goal of the town residents and the church is to resist the attack of the demon world

## A Resident's "Soul"

Every single resident (the resident means the npc or agent that driven by the generative models/llm) are constructing by following dimensions:

1. Brain: The static LLM model. Because of the restraints of techniques, the model is static and cannot be updated during a resident's life.
2. Memory: A memory stream. The data structure is designing, while it needs consider the limitation of the memory.
3. Concepts: It is the core of a resident:
   1. Ego: The idea of who am I, where am I.
   2. Goal: The idea of dream, ideal partner, etc.
   3. Memory Abstraction: The understanding of one's memory, one's past.
4. Physical Body: This is the top-down design, which cannot be modified by the resident him/herself.

## World Settings

### Residents

The residents are the people living in the virtual world.

Three kinds of residents:

* Human: The humans live in viliges and towns. Humans have intelligence.
* Creatures: The creatures have no intelligence or limit intelligence, and live in certain areas.
* Monsters: The monsters have intelligence, and strong willing to kill humans.

### User

User can dive into the world to communicate with the residents.

### Areas
