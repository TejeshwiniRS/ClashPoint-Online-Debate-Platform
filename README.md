# Module 1 Group Assignment

CSCI 5117, Fall 2024, [assignment description](https://canvas.umn.edu/courses/460699/pages/project-1)

## App Info:

* Team Name: FOUR LOOPS
* App Name: ClashPoint
* App Link: (https://clashpoint.onrender.com/)

### Students

* Alexander Garduno Garcia, gardu022@umn.edu
* Reshma Rao Chandukudlu Hosamane, chand950@umn.edu
* Tejeshwini Ramesh Subasri, rames189@umn.edu
* Shivank Sapra, sapra013@umn.edu

## Key Features

**Describe the most challenging features you implemented
(one sentence per bullet, maximum 4 bullets):**
* Implemented a client-side toxicity moderator using TensorFlow.js to evaluate user input in real time.

* Built a recommended clashes to suggest related arguments based on shared tags.

* Developed a daily cron job to automatically close arguments reaching their end date.

* Designed a scoring algorithm that calculates argument scores based on vote distributions.

* ...

## Testing Notes

**Is there anything special we need to know in order to effectively test your app? (optional):**

* ...


## Screenshots of Site

**[Add a screenshot of each key page (around 4)](https://stackoverflow.com/questions/10189356/how-to-add-screenshot-to-readmes-in-github-repository)
along with a very brief caption:**

<img width="1916" height="686" alt="image" src="https://github.com/user-attachments/assets/be863aaa-d60d-4bf2-91cf-6ba09693fc54" />
Client-side toxicity moderator: Used TensorFlow.js to run a lightweight ML model directly in the browser, analyzing user input as they type and flagging toxic or offensive language before submission.

<img width="400" height="500" alt="image" src="https://github.com/user-attachments/assets/3ee82cb8-607f-458e-ba0b-63f82e6adbaf" />
Related clashes recommender: Implemented a tag-based similarity engine that fetches and displays arguments with overlapping or related topics to improve engagement and content discovery.

<img width="1344" height="328" alt="Screenshot 2025-10-22 at 12 40 39 AM" src="https://github.com/user-attachments/assets/97c6b9ee-ecee-45e6-ad16-4d9e051e216e" />
Daily cron job for closures: Set up a scheduled background task that runs every night at 11:55 to automatically mark arguments as closed once their end date is reached, keeping data consistent.

<img width="1916" height="698" alt="image" src="https://github.com/user-attachments/assets/97408bed-f6bd-4f5f-902f-48a710a9983e" />
Custom scoring algorithm: Designed a weighted formula that dynamically updates each argument’s score based on upvotes, downvotes to reflect community consensus accurately.

## Mock-up 

There are a few tools for mock-ups. Paper prototypes (low-tech, but effective and cheap), Digital picture edition software (gimp / photoshop / etc.), or dedicated tools like moqups.com (I'm calling out moqups here in particular since it seems to strike the best balance between "easy-to-use" and "wants your money" -- the free teir isn't perfect, but it should be sufficient for our needs with a little "creative layout" to get around the page-limit)

In this space please either provide images (around 4) showing your prototypes, OR, a link to an online hosted mock-up tool like moqups.com


**[Link to the Mock-ups](https://app.moqups.com/dijouBxvfcULxMFFAq7QwonypkzUq0su/view/page/a92f8b799)**

Note: Please zoom in and out each page to view the full flow and there are 3 pages in total.


## External Dependencies

**Document integrations with 3rd Party code or services here.
Please do not document required libraries. or libraries that are mentioned in the product requirements**

* Library or service name: description of use
* ...

**If there's anything else you would like to disclose about how your project
relied on external code, expertise, or anything else, please disclose that
here:**

...
