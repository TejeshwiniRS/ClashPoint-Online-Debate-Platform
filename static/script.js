document.addEventListener("DOMContentLoaded", () => { 
  const form = document.querySelector(".landing-filters");
  const searchBtn = document.getElementById("search-btn");
  const dateWarning = document.getElementById("date-warning");


  function setDateError(msg) {
    if (!dateWarning) return;
    if (msg) {
      dateWarning.textContent = msg;
      dateWarning.classList.remove('is-hidden');
    } else {
      dateWarning.textContent = '';
      dateWarning.classList.add('is-hidden');
    }
  }

  function checkFormValidity() {
    if (!form) return;

    const query  = form.querySelector("[name='query']").value.trim();
    const sort   = form.querySelector("[name='sort']").value;
    const status = form.querySelector("[name='status']").value;
    const start  = form.querySelector("[name='start_date']").value;
    const end    = form.querySelector("[name='end_date']").value;

    let anyValue     = query || sort || status || (start && end);
    let invalidPair  = (start && !end) || (!start && end);
    let invalidOrder = false;

    if (start && end) {
      const s = new Date(start);
      const e = new Date(end);
      invalidOrder = (e <= s);
    }

    // highlight invalid date inputs
    const dateInputs = form.querySelectorAll(".landing-date");
    if (invalidPair || invalidOrder) {
      dateInputs.forEach(i => i.classList.add("invalid"));
    } else {
      dateInputs.forEach(i => i.classList.remove("invalid"));
    }

    if (invalidPair) {
      setDateError("Please select both start and end dates.");
      if (searchBtn) searchBtn.disabled = true;
      return;
    } else if (invalidOrder) {
      setDateError("End date must be later than start date.");
      if (searchBtn) searchBtn.disabled = true;
      return;
    } else {
      setDateError("");
    }

    if (searchBtn) searchBtn.disabled = !anyValue;
  }

  if (form) {
    ["query", "sort", "status", "start_date", "end_date"].forEach(name => {
      const input = form.querySelector(`[name='${name}']`);
      if (input) input.addEventListener("input", checkFormValidity);
    });
    checkFormValidity();
  }


  const deleteBtn = document.getElementById("deleteBtn");
  const cancelDelete = document.getElementById("cancelDelete");
  const deleteModal = document.getElementById("deleteModal");

  if (deleteBtn && cancelDelete && deleteModal) {
    deleteBtn.addEventListener("click", () => {
      deleteModal.style.display = "flex";
    });

    cancelDelete.addEventListener("click", () => {
      deleteModal.style.display = "none";
    });

    // Close modal if user clicks outside
    deleteModal.addEventListener("click", (e) => {
      if (e.target === deleteModal) {
        deleteModal.style.display = "none";
      }
    });
  }


  window.openJoinModal = function (id) {
    const modal = document.getElementById('joinModal');
    const form = document.getElementById('joinForm');
    if (form) form.action = `/join_community/${id}`;
    if (modal) modal.classList.add('active');
  }

  window.closeJoinModal = function () {
    const modal = document.getElementById('joinModal');
    if (modal) modal.classList.remove('active');
  }

  window.addEventListener('load', () => {
    setTimeout(() => {
      document.querySelectorAll('.flash').forEach(f => {
        f.style.transition = "opacity 0.5s ease";
        f.style.opacity = "0";
        setTimeout(() => f.remove(), 500);
      });
    }, 4000);
  });
  // --- Safe modal handling for "Remove Member" ---
    window.openRemoveModal = function () {
      const emailInput = document.getElementById("removeEmail");
      if (!emailInput) return;

      const email = emailInput.value.trim();
      if (!email) {
        alert("Please enter an email address to remove.");
        return;
      }

      // Dynamically send the POST request using Fetch
      const communityId = window.location.pathname.split("/community/")[1]?.split("/")[0];
      if (!communityId) return;

      fetch(`/community/${communityId}/remove_member`, {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: new URLSearchParams({ email }),
      })
      .then(res => {
        if (res.redirected) {
          window.location.href = res.url;
        } else {
          window.location.reload();
        }
      })
      .catch(err => console.error("Error removing member:", err));
    };



 document.querySelectorAll(".card-desc").forEach(desc => {
    const url = desc.dataset.url;

    // make text clickable
    if (url) {
      desc.addEventListener("click", (e) => {
        e.stopPropagation();
        window.location.href = url;
      });
    }

    // check if text overflows its box
    const isOverflowing = desc.scrollHeight > desc.clientHeight + 5;

    if (isOverflowing) {
      // create trailing "..." only for overflowing text
      const dots = document.createElement("span");
      dots.textContent = " ...";
      dots.style.fontWeight = "bold";
      dots.style.cursor = "pointer";

      // when clicked, go to page
      dots.addEventListener("click", (e) => {
        e.stopPropagation();
        if (url) window.location.href = url;
      });

      desc.appendChild(dots);
    }
  });
  

  // --- Search Clashes within a Community ---
  const clashSearchInput = document.getElementById('clashSearch');
  if (clashSearchInput) {
    clashSearchInput.addEventListener('input', async (e) => {
      const query = e.target.value.trim();
      const communityId = window.location.pathname.split('/').pop(); // extract ID from URL

      const res = await fetch(`/community/${communityId}/search_clashes?query=${encodeURIComponent(query)}`);
      const data = await res.json();

      const clashList = document.getElementById('clashList');
      if (!clashList) return;

      clashList.innerHTML = '';

      if (data.length === 0) {
        clashList.innerHTML = '<p>No matches found.</p>';
        return;
      }

      data.forEach(c => {
        const created = new Date(c.created_at).toLocaleDateString();
        clashList.innerHTML += `
          <div class="landing-card" style="margin-bottom: 1rem;">
            <h4>${c.title}</h4>
            <p>${c.description}</p>
            <p>Status: ${c.status.charAt(0).toUpperCase() + c.status.slice(1)} | ${created}</p>
          </div>
        `;
      });
    });
  }
});


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
      const card = btn.closest(".argument-card, .reply-card");
      const replyForm = card ? card.querySelector(".reply-form") : null;
      if (replyForm) replyForm.classList.toggle("hidden");
    });
  });
}

function initCollapseBtn() {
  // Toggle Collapse threads
  document.querySelectorAll(".collapse-btn").forEach(btn => {
    btn.addEventListener('click', () => {
        const card = btn.closest(".argument-card, .reply-card");
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
  document.querySelectorAll(".menu-btn").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      e.stopPropagation();

      // Scope to current argument or reply card
      const card = btn.closest(".argument-card, .reply-card");
      if (!card) return;

      const dropdown = card.querySelector(".menu-dropdown");
      if (!dropdown) return;

      // Toggle visibility for this menu only
      dropdown.classList.toggle("hidden");

      // Close others
      document.querySelectorAll(".menu-dropdown").forEach((d) => {
        if (d !== dropdown) d.classList.add("hidden");
      });
    });
  });

  // Close dropdown when clicking outside
  document.addEventListener("click", () => {
    document.querySelectorAll(".menu-dropdown").forEach((d) => d.classList.add("hidden"));
  });
}

function initDelete() {
   document.querySelectorAll(".delete-btn").forEach((btn) => {
    btn.addEventListener("click", async (e) => {
      e.preventDefault();
      const id = btn.dataset.id;
      if (!id || !confirm("Are you sure you want to delete this argument?")) return;

      try {
        const res = await fetch(`/argument/${id}/delete`, { method: "POST" });
        if (res.ok) {
          const card = document.querySelector(`#arg-${id}, #reply-${id}`);
          if (card) {
            const textEl = card.querySelector(".argument-text");
            const formBtns = card.querySelectorAll(".vote-btn, .reply-toggle, .menu-btn");

            if (textEl) {
              textEl.innerHTML = "<i>Argument deleted by user</i>";
              textEl.classList.add("deleted");
            }
            formBtns.forEach((b) => (b.disabled = true));
          }
        } else {
          console.error("Delete failed:", res.statusText);
        }
      } catch (err) {
        console.error("Delete error:", err);
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

function confirmDelete(event, clashTitle) {
  event.preventDefault(); // stop the link immediately
  const confirmed = confirm(`Are you sure you want to delete "${clashTitle}"?`);
  if (confirmed) {
    window.location.href = event.currentTarget.href; // proceed to delete
  } else {
    console.log("Delete cancelled");
  }
  return false;
}

// function initEditModal() {
//   const modal = document.getElementById("editModal");
//   const textarea = document.getElementById("editContent");
//   const saveBtn = document.getElementById("saveEditBtn");
//   const cancelBtn = document.getElementById("cancelEditBtn");
//   const toxWarning = document.getElementById("toxicity-warning");

//   let currentId = null;
//   let currentTextEl = null;

//   // Open modal when Edit is clicked

  
//   document.addEventListener("click", (e) => {
//     const btn = e.target.closest(".menu-edit");
//     if (!btn) return;
//     e.preventDefault();

//     currentId = btn.dataset.id;
//     currentTextEl = document.querySelector(`#text-${currentId}`);
//     if (!currentTextEl) return;

//     textarea.value = currentTextEl.textContent.trim();
//     toxWarning.classList.add("hidden");
//     modal.classList.remove("hidden");
//   });

//   // toxicity monitoring - defined above
//   watchToxicity(textarea);


//   saveBtn.addEventListener("click", async () => {
//     const content = textarea.value.trim();
//     if (!content) return alert("Content cannot be empty.");

//     try {
//       const res = await fetch(`/argument/${currentId}/edit`, {
//         method: "POST",
//         headers: { "Content-Type": "application/x-www-form-urlencoded" },
//         body: new URLSearchParams({ content })
//       });

//       if (!res.ok) throw new Error(`HTTP ${res.status}`);
//       const data = await res.json();
//       if (!data.success) throw new Error(data.error || "Edit failed");

//       if (currentTextEl) {
//         currentTextEl.textContent = data.content;
//         currentTextEl.style.transition = "background 0.3s ease";
//         setTimeout(() => currentTextEl.style.backgroundColor = "transparent", 600);

//       }

//       modal.classList.add("hidden");
//       currentId = null;
//       currentTextEl = null;
//     } catch (err) {
//       console.error("Edit error:", err);
//       alert("Could not save changes. Please try again.");
//     }
//   });

//   cancelBtn.addEventListener("click", () => modal.classList.add("hidden"));
//   modal.addEventListener("click", (e) => {
//     if (e.target === modal) modal.classList.add("hidden");
//   });
// }   
let currentId = null;
let currentTextEl = null;

function initEditModal() {
  const modal = document.getElementById("editModal");
  const modalContent = document.getElementById("editContent");
  const saveBtn = document.getElementById("saveEdit");
  const cancelBtn = document.getElementById("cancelEdit");

  if (!modal) return;

  // Open modal when clicking edit
  document.querySelectorAll(".menu-edit").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      e.preventDefault();
      const card = btn.closest(".argument-card, .reply-card");
      currentId = btn.dataset.id;

      // Get text field inside this card
      currentTextEl = card.querySelector(".argument-text");
      if (!currentTextEl) return;

      modalContent.value = currentTextEl.textContent.trim();
      modal.classList.remove("hidden");
      modal.style.display = "flex";

      // Apply toxicity watch to modal text area
      if (typeof watchToxicity === "function") {
        watchToxicity();
      }
    });
  });

  // Save changes
  saveBtn.addEventListener("click", async () => {
    const newText = modalContent.value.trim();
    if (!newText || !currentId) return;

    try {
      const res = await fetch(`/argument/${currentId}/edit`, {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: `content=${encodeURIComponent(newText)}`,
      });

      if (res.ok) {
        const card = document.querySelector(`#arg-${currentId}, #reply-${currentId}`);
        if (card) {
          const textEl = card.querySelector(".argument-text");
          if (textEl) {
            textEl.textContent = newText;
          }
        }
      } else {
        console.error("Edit failed:", res.statusText);
      }
    } catch (err) {
      console.error("Error:", err);
    } finally {
      modal.classList.add("hidden");
      modal.style.display = "none";
      currentId = null;
    }
  });

  cancelBtn.addEventListener("click", () => {
    modal.classList.add("hidden");
    modal.style.display = "none";
  });
}