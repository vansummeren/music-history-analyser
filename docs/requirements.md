# Original Requirements

> This document preserves the original problem statement as provided at project inception.

---

## Instructions

We need to split this task up in smaller chunks which can then be worked on in different session.
As a first step lay out a plan with architecture description and decisions, tasks to be taken up in their own session.
Split the work in a way it can easily be implemented and tested. Step by step.
Create a an appropriate file structure first and also start with the documentation already.

---

## The Bigger Picture

I want to build an application which allows the analysis of the play history of a user on a music service.
The main idea is to detect inappropriate artists or songs using an AI.

For the first release we focus on spotify.

The application will be a web application, deployed as a docker container.

The application shall be visually appealing with a modern, clean look. Use graphics where needed.

---

## Specification

### Features

- Login with a configurable SAML/OIDC back end only, no unauthorized access. Authenticated users can login, a user profile is created with the first login.
- The user can link one or more spotify accounts.
- The user can also access AI models like Claude, Perplexity through their API.
- The user can link one of the music accounts with an AI and provide a prompt which will be sent to the AI with the list of the songs listened to.
- The user can configure multiple of these analyses.
- The analysis can be scheduled so that for instance every week the listening history is downloaded and sent for analysis. When scheduling, the time frame of the history can be specified, i.e. "the last week", etc.
- A result of the analysis is sent to a defined email address.
- The user should be able to logout.

**Tech stack:**
Choose what you find is appropriate. It should be well maintainable and not waste any resources, CPU and memory/storage.
We probably also also need a database backend to store some application state and config.

---

### Hosting

The application will be hosted on docker.
I want the different components to be split, they shall run in different containers:
- Database
- Backend (web app)

Make sure communication between web app and database is properly secured and authenticated.
For the ingress I eventually want to use a cloudflare tunnel. Build the stack in a way this is easily possible; cloudflared does not need to be part of this.
Prepare a docker-compose.yml so it's easy to run it.

---

### Pipelines

Also include the required pipelines to build, test, and deploy the application. Deployment means pushing it to a repository from where it can be installed on a docker host.

---

### Non-functional Requirements

- Develop the application in a secure way, validate user input, don't use outdated libraries, no exotic dependencies, keep it simple and well tested.
- Make it expandable so we can for instance add more music providers or AI backends later.
- Write unit tests to verify the proper functioning of the code and to avoid regression.
