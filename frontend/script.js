document.addEventListener("DOMContentLoaded", () => {
    // --- AUTHENTICATION ELEMENTS ---
    const loginContainer = document.getElementById('login-container');
    const chatAppContainer = document.getElementById('chat-app-container');
    const formTitle = document.getElementById('form-title');
    const usernameInput = document.getElementById('username');
    const passwordInput = document.getElementById('password');
    const authBtn = document.getElementById('auth-btn');
    const toggleLink = document.getElementById('toggle-link');
    const toggleMessage = document.getElementById('toggle-message');
    const authError = document.getElementById('auth-error');

    // --- CHATBOT ELEMENTS ---
    const chatBox = document.getElementById('chat-box');
    const userInput = document.getElementById('user-input');
    const sendBtn = document.getElementById('send-btn');
    const logoutBtn = document.getElementById('logout-btn');
    const typingIndicator = document.getElementById('typing-indicator');
    const themeToggle = document.getElementById('theme-toggle');
    const welcomeUser = document.getElementById('welcome-user');

    let isLoginMode = true;
    let loggedInUsername = null;
    let userData = {};
    let conversationState = 'idle';
    let lastUserQuestion = "";

    const questions = {
        'asking_gre': 'To start, what is your GRE Score (out of 340)?',
        'asking_toefl': 'Next, what is your TOEFL Score (out of 120)?',
        'asking_sop': "How would you rate your Statement of Purpose? (e.g., Average, Good, or Excellent)",
        'asking_lor': "Are your Letters of Recommendation from strong sources? (e.g., Yes or No)",
        'asking_cgpa': 'What is your Undergraduate CGPA (out of 10)?',
        'asking_research': 'Finally, do you have research experience? (Enter 1 for Yes, 0 for No)',
    };

    function addMessage(htmlContent, sender, showFeedback = false) {
        const messageElement = document.createElement('div');
        messageElement.classList.add('message', `${sender}-message`);
        messageElement.innerHTML = sender === 'bot' ? marked.parse(htmlContent) : htmlContent;
        if (sender === 'bot' && showFeedback) {
            const feedbackContainer = document.createElement('div');
            feedbackContainer.classList.add('feedback-buttons');
            feedbackContainer.innerHTML = `<button class="feedback-btn" data-rating="1" title="Good response"><i class="fa-solid fa-thumbs-up"></i></button><button class="feedback-btn" data-rating="-1" title="Bad response"><i class="fa-solid fa-thumbs-down"></i></button>`;
            messageElement.appendChild(feedbackContainer);
        }
        chatBox.appendChild(messageElement);
        chatBox.scrollTop = chatBox.scrollHeight;
    }

    function showTypingIndicator() {
        typingIndicator.style.display = 'flex';
        chatBox.scrollTop = chatBox.scrollHeight;
    }

    function hideTypingIndicator() {
        typingIndicator.style.display = 'none';
    }

    async function getAiResponse(message, profile = null) {
    showTypingIndicator();
    try {
        const isQAResponse = !profile;
        const response = await fetch('/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username: loggedInUsername, question: message, profile: profile }),
        });

        const result = await response.json();
        
        if (!response.ok) {
            // This will now grab the helpful error from our server
            throw new Error(result.error || `An unknown error occurred.`);
        }
        
        addMessage(result.answer, 'bot', isQAResponse);
        
        if (conversationState !== 'idle') {
            conversationState = 'idle';
            userInput.placeholder = "Ask another question...";
        }
    } catch (error) {
        // --- THIS IS THE FIX ---
        // Instead of a generic message, we now show the actual error.
        addMessage(error.message, 'bot');
    } finally {
        hideTypingIndicator();
    }
}
    function handleUserInput() {
        const userText = userInput.value.trim();
        if (userText === '') return;
        lastUserQuestion = userText;
        addMessage(userText, 'user');
        userInput.value = '';
        if (conversationState === 'idle') {
            getAiResponse(userText);
        } else {
            handleGuidedConversation(userText);
        }
    }

    async function handleFeedbackClick(event) {
        const button = event.target.closest('.feedback-btn');
        if (!button) return;
        const rating = parseInt(button.dataset.rating, 10);
        const feedbackContainer = button.parentElement;
        const messageElement = feedbackContainer.closest('.bot-message');
        const answerContent = messageElement.cloneNode(true);
        answerContent.querySelector('.feedback-buttons').remove();
        const answer = answerContent.innerHTML;
        try {
            const response = await fetch('/feedback', { // REMOVED HARDCODED URL
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    username: loggedInUsername,
                    question: lastUserQuestion,
                    answer: answer,
                    rating: rating
                }),
            });
            if (response.ok) {
                feedbackContainer.classList.add('disabled');
                button.classList.add('clicked');
            } else { console.error("Failed to submit feedback."); }
        } catch (error) { console.error("Error submitting feedback:", error); }
    }

    function setAuthMode(isLogin) {
        isLoginMode = isLogin;
        formTitle.textContent = isLogin ? 'Login' : 'Register';
        authBtn.textContent = isLogin ? 'Login' : 'Register';
        toggleMessage.textContent = isLogin ? "Don't have an account?" : "Already have an account?";
        toggleLink.textContent = isLogin ? 'Register' : 'Login';
        authError.textContent = '';
    }

    async function authBtnClickHandler() {
        const username = usernameInput.value.trim();
        const password = passwordInput.value.trim();
        if (!username || !password) {
            authError.textContent = 'Username and password are required.';
            return;
        }
        const endpoint = isLoginMode ? '/login' : '/register';
        try {
            const response = await fetch(endpoint, { // REMOVED HARDCODED URL
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ username, password }),
            });
            const result = await response.json();
            if (result.success) {
                if (isLoginMode) {
                    initializeChat(username);
                } else {
                    authError.textContent = 'Registration successful! Please login.';
                    setAuthMode(true);
                }
            } else {
                authError.textContent = result.message || 'An error occurred.';
            }
        } catch (error) {
            authError.textContent = 'Could not connect to the server.';
        }
    }

    function initializeChat(username) {
        loggedInUsername = username;
        loginContainer.style.display = 'none';
        chatAppContainer.style.display = 'block';
        welcomeUser.textContent = `Welcome, ${username}!`;
        startNewConversation();
    }

    function logout() {
        loggedInUsername = null;
        chatAppContainer.style.display = 'none';
        loginContainer.style.display = 'flex';
        usernameInput.value = '';
        passwordInput.value = '';
        setAuthMode(true);
    }
    
    function setTheme(theme) {
        if (theme === 'dark') {
            document.body.setAttribute('data-theme', 'dark');
            localStorage.setItem('theme', 'dark');
            themeToggle.checked = true;
        } else {
            document.body.removeAttribute('data-theme');
            localStorage.setItem('theme', 'light');
            themeToggle.checked = false;
        }
    }
    
    function handleGuidedConversation(userText) {
        switch (conversationState) {
            case 'asking_gre': userData.gre_score = parseInt(userText, 10); conversationState = 'asking_toefl'; break;
            case 'asking_toefl': userData.toefl_score = parseInt(userText, 10); conversationState = 'asking_sop'; break;
            case 'asking_sop': userData.sop = userText.trim(); conversationState = 'asking_lor'; break;
            case 'asking_lor': userData.lor = userText.trim(); conversationState = 'asking_cgpa'; break;
            case 'asking_cgpa': userData.cgpa = parseFloat(userText); conversationState = 'asking_research'; break;
            case 'asking_research':
                userData.research = parseInt(userText, 10);
                addMessage("Thank you! Generating your personalized recommendations...", 'bot');
                getAiResponse("recommendations", { ...userData });
                return;
        }
        addMessage(questions[conversationState], 'bot');
    }

    async function startNewConversation() {
        chatBox.innerHTML = '';
        userData = {};
        conversationState = 'idle';
        userInput.placeholder = "Ask a question...";
        try {
            const response = await fetch('/get_profile', { // REMOVED HARDCODED URL
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ username: loggedInUsername }),
            });
            const data = await response.json();
            if (data.profile_found) {
                userData = data.profile;
                const welcomeBackMsg = `Welcome back, ${loggedInUsername}! I've found your saved profile. Would you like to get new recommendations with this profile?<br><br><button id="use-profile-btn" class="choice-btn">Yes, Get Recommendations</button><button id="start-new-profile-btn" class="choice-btn">No, Start a New Profile</button>`;
                addMessage(welcomeBackMsg, 'bot');
            } else {
                const greeting = `Hello, ${loggedInUsername}! I can answer questions about admissions. When you're ready, click to get personalized university recommendations.<br><br><button id="start-rec-btn" class="choice-btn">Get Personalised Recommendations</button>`;
                addMessage(greeting, 'bot');
            }
        } catch (error) {
            addMessage(`Could not connect to the server.`, 'bot');
        }
    }

    toggleLink.addEventListener('click', (e) => {
        e.preventDefault();
        setAuthMode(!isLoginMode);
    });
    authBtn.addEventListener('click', authBtnClickHandler);
    usernameInput.addEventListener('keyup', (event) => {
        if (event.key === 'Enter') { authBtn.click(); }
    });
    passwordInput.addEventListener('keyup', (event) => {
        if (event.key === 'Enter') { authBtn.click(); }
    });
    chatBox.addEventListener('click', async function(event) {
        const targetId = event.target.id;
        if (targetId === 'start-rec-btn' || targetId === 'start-new-profile-btn') {
            conversationState = 'asking_gre';
            addMessage(questions.asking_gre, 'bot');
            userInput.placeholder = "Enter your profile details...";
            event.target.parentElement.innerHTML = "Great, let's build your profile.";
        } else if (targetId === 'use-profile-btn') {
            addMessage("Excellent! Using your saved profile to generate new recommendations...", 'user');
            getAiResponse("recommendations", userData);
            event.target.parentElement.innerHTML = "Using your saved profile.";
        }
        handleFeedbackClick(event);
    });
    sendBtn.addEventListener('click', handleUserInput);
    userInput.addEventListener('keyup', (event) => { if (event.key === 'Enter') { handleUserInput(); } });
    logoutBtn.addEventListener('click', logout);
    if(localStorage.getItem('theme')) { setTheme(localStorage.getItem('theme')); }
    themeToggle.addEventListener('change', () => setTheme(themeToggle.checked ? 'dark' : 'light'));
});