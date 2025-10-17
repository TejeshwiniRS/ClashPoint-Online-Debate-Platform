const form = document.querySelector(".landing-filters");
const searchBtn = document.getElementById("search-btn");
const dateWarning = document.getElementById("date-warning");

function setDateError(msg) {
  if (msg) {
    dateWarning.textContent = msg;
    dateWarning.classList.remove('is-hidden');
  } else {
    dateWarning.textContent = '';
    dateWarning.classList.add('is-hidden');
  }
}

function checkFormValidity() {
  const query = form.querySelector("[name='query']").value.trim();
  const sort = form.querySelector("[name='sort']").value;
  const status = form.querySelector("[name='status']").value;
  const start = form.querySelector("[name='start_date']").value;
  const end   = form.querySelector("[name='end_date']").value;

  let anyValue = query || sort || status || (start && end);
  let invalidPair   = (start && !end) || (!start && end);
  let invalidOrder  = false;

  if (start && end) {
    const s = new Date(start);
    const e = new Date(end);
    invalidOrder = (e <= s);
  }

  // visual input state
  const dateInputs = form.querySelectorAll(".landing-date");
  if (invalidPair || invalidOrder) {
    dateInputs.forEach(i => i.classList.add("invalid"));
  } else {
    dateInputs.forEach(i => i.classList.remove("invalid"));
  }

  if (invalidPair) {
    setDateError("Please select both start and end dates.");
    searchBtn.disabled = true;
    return;
  } else if (invalidOrder) {
    setDateError("End date must be later than start date.");
    searchBtn.disabled = true;
    return;
  } else {
    setDateError("");
  }

  searchBtn.disabled = !anyValue;
}

if (form) {
  ["query","sort","status","start_date","end_date"].forEach(name => {
    const input = form.querySelector(`[name='${name}']`);
    if (input) input.addEventListener("input", checkFormValidity);
  });

  checkFormValidity();
}



// ============================
// PROFILE PAGE INTERACTIONS
// ============================
document.addEventListener("DOMContentLoaded", () => {
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

    // Optional: close modal when clicking outside
    deleteModal.addEventListener("click", (e) => {
      if (e.target === deleteModal) {
        deleteModal.style.display = "none";
      }
    });
  }
});
