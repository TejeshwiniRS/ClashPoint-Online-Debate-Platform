let toxicityModel;
async function initToxicityModel(){
  const threshold = 0.85;
  toxicityModel = await toxicity.load(threshold)
  console.log("Toxicity Model loaded")
}

function watchToxicity(targetElement = null) {
  const fields = targetElement 
    ? [targetElement] 
    : document.querySelectorAll("textarea[name='content'], #editContent");

  fields.forEach(field => {
    field.addEventListener("input", async () => {
      const text = field.value.trim();
      if (!toxicityModel || text.length < 5) {
        const warn = field.parentElement.querySelector(".toxicity-warning");
        if (warn) warn.remove();
        return;
      }

      const preds = await toxicityModel.classify([text]);
      const toxic = preds.some(p => p.results[0].match);
      let warn = field.parentElement.querySelector(".toxicity-warning");

      if (toxic) {
        if (!warn) {
          warn = document.createElement("p");
          warn.className = "toxicity-warning";
          warn.style.color = "red";
          warn.style.marginTop = "0.5rem";
          warn.textContent = "⚠️ This message may be toxic — please rephrase.";
          field.parentElement.appendChild(warn);
        //   const modalSave = document.getElementById("saveEditBtn");
        // if (modalSave) modalSave.disabled = toxic;
        }
        setFormButtonsDisabled(field, true);
        
      } else if (warn) {
        warn.remove();
        setFormButtonsDisabled(field, false);

      }
    });
  });
}


function setFormButtonsDisabled(field, disabled) {
  const form = field.closest("form");
  if (!form) return;
  form
    .querySelectorAll('button[type="submit"], button[name="argument_type"]')
    .forEach((btn) => (btn.disabled = disabled));
}


document.addEventListener("DOMContentLoaded", () => {
  
  initTabs();
  initVotes();
  initReplyToggle();
  initCollapseBtn();
  initReadMore();
  initDropdown();
  initDelete();  
  initPost();
  (async () => {
    await initToxicityModel();
    watchToxicity();
  })();
  initEditModal();
});

function initTabs(){
  // tabbed view
  const tabLinks = document.querySelectorAll(".tab-link");
  const tabContents = document.querySelectorAll(".tab-content");

   // Restore active tab 
  const savedTab = localStorage.getItem("activeTab");
  if (savedTab) {
    tabLinks.forEach(l => l.classList.remove("active"));
    tabContents.forEach(c => c.classList.remove("active"));
    document.querySelector(`[data-tab='${savedTab}']`)?.classList.add("active");
    document.getElementById(savedTab)?.classList.add("active");
  }

  tabLinks.forEach(link => {
    link.addEventListener("click", () => {
      // Remove active state
      tabLinks.forEach(l => l.classList.remove("active"));
      tabContents.forEach(c => c.classList.remove("active"));

      // Activate clicked tab
      link.classList.add("active");
      const target = document.getElementById(link.dataset.tab);
      if (target) target.classList.add("active");

      // Save active tab
      localStorage.setItem("activeTab", link.dataset.tab);
    });
  });
}

function initVotes(){
  // Handle votes
  document.querySelectorAll(".vote-form").forEach(form => {
    form.querySelectorAll(".vote-btn").forEach(btn => {
      btn.addEventListener("click", async (e) => {
        e.preventDefault();

        const id = btn.dataset.id;
        const vote = btn.dataset.vote;

        const formData = new FormData();
        formData.append("vote", vote);

        try {
          const res = await fetch(`/argument/${id}/vote`, {
            method: "POST",
            body: formData,
          });

          if (!res.ok) {
            console.error("Vote failed:", res.status);
            return;
          }
          const data = await res.json();

          const scoreEl = document.getElementById(`score-${id}`);
          const upEl = document.getElementById(`up-${id}`);
          const downEl = document.getElementById(`down-${id}`);

          if (scoreEl) scoreEl.textContent = data.score;
          if (upEl) upEl.textContent = data.up_votes;
          if (downEl) downEl.textContent = data.down_votes;

        } catch (err) {
          console.error("Error:", err);
        }
      });
    });
  });
}

function initReplyToggle(){
  // Handle reply form toggle
  document.querySelectorAll(".reply-toggle").forEach(btn => {
    btn.addEventListener("click", (e) => {
      e.preventDefault();
      const card = btn.closest(".argument-card, .reply-item");
      const replyForm = card ? card.querySelector(".reply-form") : null;
      if (replyForm) replyForm.classList.toggle("hidden");
    });
  });
}

function initCollapseBtn() {
  // Toggle Collapse threads
  document.querySelectorAll(".collapse-btn").forEach(btn => {
    btn.addEventListener('click', () => {
        const card = btn.closest(".argument-card, .reply-item");
        const isCollapsed = btn.dataset.collapsed === "true";

        btn.dataset.collapsed = (!isCollapsed).toString();
        btn.textContent = isCollapsed ? "▼" : "▶";

        const replies = card.querySelectorAll(".reply-block");
        replies.forEach(r => {
            r.style.display = isCollapsed ? "" : "none";
        });
        
        const readMore = card.querySelector(".read-more-container");
        const text = card.querySelector(".argument-text");
        if(text){
            text.style.display = isCollapsed ? "" : "none";
            readMore.style.display = isCollapsed ? "" : "none";
        }
        const meta = card.querySelector(".argument-meta");
        if(meta)
            meta.style.display = isCollapsed ? "" : "none";   
        const actionRow = card.querySelector(".action-row");
        if(actionRow)
            actionRow.style.display = isCollapsed ? "" : "none";        
    });
  });
}

function initReadMore(){
  //   Read More functionality for long text
  document.querySelectorAll(".argument-text").forEach(textEle =>{
    const fullText = textEle.textContent.trim();

    MAX_CHARS = 300;
    if(fullText.length > MAX_CHARS){
        const shortText = fullText.slice(0, MAX_CHARS);
        textEle.textContent = shortText + " ...";
        
        const id = textEle.id.replace("text-", "");
        const readMore = document.getElementById(`read-more-${id}`);
        
        if(readMore){
            readMore.classList.remove("hidden");
            readMore.textContent = "Read More...";
        }

        let expanded = false;

        readMore?.addEventListener("click", () => {
            expanded = !expanded;
            if(expanded){
              textEle.textContent = fullText;
              readMore.textContent = "Read Less";
            } else{
              textEle.textContent = shortText + " ...";
              readMore.textContent = "Read More ...";
            }
        });
    }
  });

}

function initDropdown(){
  // function to handle dropdown functionality
  document.querySelectorAll(".menu-btn").forEach(btn => {
    btn.addEventListener("click", e => {
      e.stopPropagation();
      const dropdown = btn.nextElementSibling;
      dropdown.classList.toggle("hidden");

      // Close other menus
      document.querySelectorAll(".menu-dropdown").forEach(d => {
        if (d !== dropdown) d.classList.add("hidden");
      });
    });
  });

  // Close dropdown when clicking outside
  document.addEventListener("click", () => {
    document.querySelectorAll(".menu-dropdown").forEach(d => d.classList.add("hidden"));
  });

}

function initDelete() {
  document.querySelectorAll(".delete-btn").forEach(btn => {
    btn.addEventListener("click", async (e) => {
      e.preventDefault();
      e.stopPropagation();

      if (!confirm("Are you sure you want to delete this post?")) return;

      const id = btn.dataset.id;

      try {
        const res = await fetch(`/argument/${id}/delete`, { method: "POST" });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();

        if (!data.success) {
          alert(data.error || "Delete failed — please try again.");
          return;
        }

        const card = document.getElementById(`arg-${id}`);
        if (!card) return;

        card.classList.add("deleted");

        // Replace the text content with deleted placeholder text
        const textEl = card.querySelector(".argument-text");
        if (textEl) {
          textEl.textContent = card.classList.contains("reply-item")
            ? "Reply deleted by user"
            : "Argument deleted by user";
          textEl.classList.add("deleted-text");
        }

        //Disable all interactions for this card
        card.querySelectorAll(
          ".vote-btn, .reply-toggle, .menu-edit, .delete-btn, .read-more"
        ).forEach(el => {
          el.disabled = true;
          el.classList.add("disabled");
          el.style.pointerEvents = "none";
        });

        const replyForm = card.querySelector(".reply-form");
        if (replyForm) replyForm.classList.add("hidden");

        const readMore = card.querySelector(".read-more-container");
        if (readMore) readMore.classList.add("hidden");

        const actionRow = card.querySelector(":scope .action-row");
        if (actionRow) actionRow.classList.add("hidden");

        card.style.transition = "background 0.3s ease";
        card.style.backgroundColor = "#f8f8f8";

      } catch (err) {
        console.error("Delete error:", err);
        alert("Something went wrong while deleting. Please refresh and try again.");
      }
    });
  });
}

function initPost() {
  document.querySelectorAll(".post-argument-form").forEach(form => {
    let clickedButton = null;

    // Trackoing which button is clicked
    form.querySelectorAll("button[name='argument_type']").forEach(btn => {
      btn.addEventListener("click", () => {
        clickedButton = btn.value; 
      });
    });

    form.addEventListener("submit", async (e) => {
      e.preventDefault();

      const clashId = form.dataset.clashId;
      const formData = new FormData(form);


      if (clickedButton) formData.set("argument_type", clickedButton);

      try {
        const res = await fetch(`/clash/${clashId}/post`, {
          method: "POST",
          body: formData
        });

        if (!res.ok) throw new Error(`HTTP ${res.status}`);

        const html = await res.text();

        // Create temp element to extract new card
        const temp = document.createElement("div");
        temp.innerHTML = html.trim();
        const newCard = temp.firstElementChild;

        // Add card to correct tab
        const container = document.querySelector(
          clickedButton === "for" ? "#for-tab" : "#against-tab"
        );
        if (container) container.prepend(newCard);
        form.reset();
        clickedButton = null;

      } catch (err) {
        console.error("Post error:", err);
        alert("Something went wrong while posting.");
      }
    });
  });
}

function initEditModal() {
  const modal = document.getElementById("editModal");
  const textarea = document.getElementById("editContent");
  const saveBtn = document.getElementById("saveEditBtn");
  const cancelBtn = document.getElementById("cancelEditBtn");
  const toxWarning = document.getElementById("toxicity-warning");

  let currentId = null;
  let currentTextEl = null;

  // Open modal when Edit is clicked
  document.addEventListener("click", (e) => {
    const btn = e.target.closest(".menu-edit");
    if (!btn) return;
    e.preventDefault();

    currentId = btn.dataset.id;
    currentTextEl = document.querySelector(`#text-${currentId}`);
    if (!currentTextEl) return;

    textarea.value = currentTextEl.textContent.trim();
    toxWarning.classList.add("hidden");
    modal.classList.remove("hidden");
  });

  // toxicity monitoring - defined above
  watchToxicity(textarea);


  saveBtn.addEventListener("click", async () => {
    const content = textarea.value.trim();
    if (!content) return alert("Content cannot be empty.");

    try {
      const res = await fetch(`/argument/${currentId}/edit`, {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: new URLSearchParams({ content })
      });

      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      if (!data.success) throw new Error(data.error || "Edit failed");

      if (currentTextEl) {
        currentTextEl.textContent = data.content;
        currentTextEl.style.transition = "background 0.3s ease";
        setTimeout(() => currentTextEl.style.backgroundColor = "transparent", 600);

      }

      modal.classList.add("hidden");
      currentId = null;
      currentTextEl = null;
    } catch (err) {
      console.error("Edit error:", err);
      alert("Could not save changes. Please try again.");
    }
  });

  cancelBtn.addEventListener("click", () => modal.classList.add("hidden"));
  modal.addEventListener("click", (e) => {
    if (e.target === modal) modal.classList.add("hidden");
  });
}   
