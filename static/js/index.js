(function () {
  const startBtn = document.getElementById("start-btn");
  const formSection = document.getElementById("form-section");
  const formMount = document.getElementById("form-mount");
  const joinForm = document.getElementById("join-form");
  const joinInput = document.getElementById("join-input");
  const joinError = document.getElementById("join-error");

  startBtn.addEventListener("click", () => {
    startBtn.classList.add("hidden");
    formSection.classList.remove("hidden");
    formSection.scrollIntoView({ behavior: "smooth" });
    renderPreferenceForm(formMount, {
      onSubmit: async (profile) => {
        const savedCode = localStorage.getItem("tonight_couple_code");
        const body = { role: "A", ...profile };
        if (savedCode) body.couple_code = savedCode;
        const data = await api.postJSON("/api/session", body);
        localStorage.setItem("tonight_couple_code", data.couple_code);
        window.location.href = `/session/${data.session_id}?role=A`;
      },
    });
  });

  joinForm.addEventListener("submit", (e) => {
    e.preventDefault();
    const id = sessionIdFromInput(joinInput.value);
    if (!id) {
      joinError.textContent = "That doesn't look like a valid link or code.";
      joinError.classList.remove("hidden");
      return;
    }
    window.location.href = `/session/${id}?role=B`;
  });
})();
