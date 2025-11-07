// Enhanced News Processing Demo - JavaScript
class EnhancedNewsDemo {
    constructor() {
        // Use relative API path for Vercel deployment, or localhost for local dev
        this.apiBase = window.location.hostname === 'localhost' 
            ? 'http://localhost:8000' 
            : window.location.origin;
        
        this.models = [];
        this.selectedModel = null;
        this.newsArticles = [];
        this.selectedArticle = null;
        this.isProcessing = false;
        this.realtimeActive = false;
        
        this.init();
    }

    async init() {
        console.log('🚀 Initializing Enhanced News Processing Demo...');
        
        // Check backend connection
        await this.checkConnection();
        
        // Load models and news
        await this.loadModels();
        await this.loadNews();
        await this.loadKeypoints();
        
        // Start auto-refresh for keypoints
        this.startAutoRefresh();
        
        console.log('✅ Enhanced demo initialized successfully');
    }

    async checkConnection() {
        try {
            const response = await fetch(`${this.apiBase}/health`);
            const data = await response.json();
            
            if (response.ok) {
                this.updateStatus(true, 'Enhanced Backend Connected', 
                    `Mode: ${data.mode} | Models: ${data.features?.model_count} | News: ${data.features?.news_articles}`);
                return true;
            } else {
                throw new Error(`Backend returned ${response.status}`);
            }
        } catch (error) {
            console.error('❌ Connection failed:', error);
            this.updateStatus(false, 'Backend Disconnected', 'Please start the enhanced backend server');
            return false;
        }
    }

    updateStatus(connected, text, details) {
        const statusDot = document.getElementById('statusDot');
        const statusText = document.getElementById('statusText');
        const statusDetails = document.getElementById('statusDetails');
        
        statusDot.className = `status-dot ${connected ? 'connected' : ''}`;
        statusText.textContent = text;
        statusDetails.textContent = details;
    }

    async loadModels() {
        try {
            const response = await fetch(`${this.apiBase}/api/models`);
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            
            const data = await response.json();
            this.models = data.models;
            this.selectedModel = data.current_model;
            
            this.displayModels();
            console.log(`🤖 Loaded ${this.models.length} STT models`);
            
        } catch (error) {
            console.error('❌ Failed to load models:', error);
            this.showError('Failed to load STT models: ' + error.message);
        }
    }

    displayModels() {
        const container = document.getElementById('modelSelector');
        
        if (!this.models || this.models.length === 0) {
            container.innerHTML = '<div class="loading">No models available</div>';
            return;
        }

        const modelsHtml = this.models.map(model => `
            <div class="model-card ${model.id === this.selectedModel ? 'selected' : ''}" 
                 onclick="demo.selectModel('${model.id}')">
                <div class="model-name">${model.name}</div>
                <div class="model-desc">${model.description}</div>
                <div class="model-stats">
                    <span class="stat-badge speed-${model.speed}">${model.speed} speed</span>
                    <span class="stat-badge accuracy-${model.accuracy.replace(' ', '-')}">${model.accuracy} accuracy</span>
                </div>
            </div>
        `).join('');

        container.innerHTML = modelsHtml;
    }

    async selectModel(modelId) {
        try {
            const response = await fetch(`${this.apiBase}/api/models/select`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ model_id: modelId })
            });

            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            
            const data = await response.json();
            this.selectedModel = modelId;
            
            // Update UI
            this.displayModels();
            this.showMessage(`🤖 Selected: ${data.selected_model.name}`, 'success');
            
            console.log(`🤖 Selected model: ${data.selected_model.name}`);
            
        } catch (error) {
            console.error('❌ Failed to select model:', error);
            this.showError('Failed to select model: ' + error.message);
        }
    }

    async loadNews() {
        try {
            const response = await fetch(`${this.apiBase}/api/news/articles`);
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            
            const data = await response.json();
            this.newsArticles = data.articles;
            
            this.displayNews();
            console.log(`📰 Loaded ${this.newsArticles.length} news articles`);
            
        } catch (error) {
            console.error('❌ Failed to load news:', error);
            this.showError('Failed to load news articles: ' + error.message);
        }
    }

    displayNews() {
        const container = document.getElementById('newsArticles');
        
        if (!this.newsArticles || this.newsArticles.length === 0) {
            container.innerHTML = '<div class="loading">No news articles available</div>';
            return;
        }

        const newsHtml = this.newsArticles.map((article, index) => `
            <div class="article-item" onclick="demo.processArticle(${index})">
                <div class="article-title">${article.title}</div>
                <div class="article-desc">${article.description}</div>
                <div class="article-meta">
                    📰 ${article.source} • 📅 ${new Date(article.publishedAt).toLocaleString()}
                </div>
            </div>
        `).join('');

        container.innerHTML = newsHtml;
    }

    async processArticle(articleIndex) {
        if (!this.selectedModel) {
            this.showError('Please select a model first');
            return;
        }

        if (this.isProcessing) {
            this.showMessage('⏳ Processing in progress, please wait...', 'info');
            return;
        }

        this.isProcessing = true;
        const article = this.newsArticles[articleIndex];
        
        try {
            this.showMessage(`🔄 Processing "${article.title}" with ${this.getModelName()}...`, 'info');
            
            const response = await fetch(`${this.apiBase}/api/process/article`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    article_index: articleIndex,
                    model_id: this.selectedModel
                })
            });

            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            
            const result = await response.json();
            
            this.displayProcessingResults(result);
            this.showMessage(`✅ Processing completed! Generated ${result.keypoints.length} keypoints`, 'success');
            
            // Refresh keypoints to show new results
            setTimeout(() => this.loadKeypoints(), 1000);
            
        } catch (error) {
            console.error('❌ Processing failed:', error);
            this.showError('Processing failed: ' + error.message);
        } finally {
            this.isProcessing = false;
        }
    }

    displayProcessingResults(result) {
        const container = document.getElementById('processingResults');
        const titleElement = document.getElementById('resultsTitle');
        const contentElement = document.getElementById('resultsContent');
        
        titleElement.textContent = `Processing Results - ${result.model_used}`;
        
        const resultsHtml = `
            <div style="margin-bottom: 20px; padding: 15px; background: #f8f9fa; border-radius: 8px;">
                <strong>📰 Article:</strong> ${result.article_title}<br>
                <strong>🤖 Model:</strong> ${result.model_used}<br>
                <strong>⏱️ Processing Time:</strong> ${result.processing_time.toFixed(2)}s<br>
                <strong>📊 Average Confidence:</strong> ${(result.confidence_avg * 100).toFixed(1)}%<br>
                <strong>📅 Processed:</strong> ${new Date(result.processed_at).toLocaleString()}
            </div>
            
            <div>
                <strong>🔑 Generated Keypoints:</strong>
                ${result.keypoints.map((kp, index) => `
                    <div class="keypoint-result" id="result-keypoint-${index}">
                        <div class="keypoint-text">${kp.keypoint_text}</div>
                        <div class="keypoint-meta">
                            <span>Keypoint #${index + 1}</span>
                            <span class="confidence-${this.getConfidenceClass(kp.confidence_score)}">
                                ${(kp.confidence_score * 100).toFixed(1)}% confidence
                            </span>
                        </div>
                        <div class="keypoint-controls">
                            <button class="audio-btn" onclick="demo.playResultKeypointAudio('${kp.keypoint_text}', ${index}, this)">
                                🔊 Listen
                            </button>
                            <span class="tts-status" id="result-tts-status-${index}"></span>
                        </div>
                        <div class="audio-player" id="result-audio-player-${index}">
                            <audio controls id="result-audio-${index}">
                                Your browser does not support the audio element.
                            </audio>
                        </div>
                    </div>
                `).join('')}
            </div>
        `;
        
        contentElement.innerHTML = resultsHtml;
        container.style.display = 'block';
        
        // Scroll to results
        container.scrollIntoView({ behavior: 'smooth' });
    }

    getConfidenceClass(score) {
        if (score >= 0.8) return 'high';
        if (score >= 0.6) return 'medium';
        return 'low';
    }

    getModelName() {
        const model = this.models.find(m => m.id === this.selectedModel);
        return model ? model.name : 'Unknown Model';
    }

    async startRealtime() {
        if (!this.selectedModel) {
            this.showError('Please select a model first');
            return;
        }

        try {
            this.showMessage('🚀 Starting real-time processing...', 'info');
            
            const response = await fetch(`${this.apiBase}/api/realtime/start`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    sources: ['news_api'],
                    model_id: this.selectedModel
                })
            });

            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            
            const result = await response.json();
            
            this.realtimeActive = true;
            this.updateRealtimeUI();
            
            this.showMessage(`✅ Real-time processing started with ${result.model.name}!`, 'success');
            
            // Start monitoring
            this.startRealtimeMonitoring();
            
        } catch (error) {
            console.error('❌ Failed to start real-time processing:', error);
            this.showError('Failed to start real-time processing: ' + error.message);
        }
    }

    async stopRealtime() {
        try {
            const response = await fetch(`${this.apiBase}/api/realtime/stop`, {
                method: 'POST'
            });

            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            
            this.realtimeActive = false;
            this.updateRealtimeUI();
            
            this.showMessage('⏹️ Real-time processing stopped', 'info');
            
        } catch (error) {
            console.error('❌ Failed to stop real-time processing:', error);
            this.showError('Failed to stop real-time processing: ' + error.message);
        }
    }

    updateRealtimeUI() {
        const startBtn = document.getElementById('startRealtimeBtn');
        const stopBtn = document.getElementById('stopRealtimeBtn');
        const status = document.getElementById('realtimeStatus');
        const info = document.getElementById('realtimeInfo');
        
        if (this.realtimeActive) {
            startBtn.disabled = true;
            stopBtn.disabled = false;
            status.textContent = `🔄 Processing with ${this.getModelName()}`;
            status.style.color = '#28a745';
            info.style.display = 'block';
        } else {
            startBtn.disabled = false;
            stopBtn.disabled = true;
            status.textContent = 'Ready to start';
            status.style.color = '#666';
            info.style.display = 'none';
        }
    }

    startRealtimeMonitoring() {
        if (!this.realtimeActive) return;
        
        this.updateRealtimeStatus();
        
        setTimeout(() => this.startRealtimeMonitoring(), 3000);
    }

    async updateRealtimeStatus() {
        try {
            const response = await fetch(`${this.apiBase}/api/realtime/status`);
            if (!response.ok) return;
            
            const status = await response.json();
            const details = document.getElementById('processingDetails');
            
            if (details && status.processor) {
                const proc = status.processor;
                details.innerHTML = `
                    <div>🤖 Model: ${proc.current_model?.name || 'Unknown'}</div>
                    <div>📊 Queue Size: ${proc.queue_size}</div>
                    <div>🔄 Active Streams: ${status.total_active_streams}</div>
                    <div>📝 Last Keypoints: ${proc.last_keypoints_count}</div>
                `;
            }
            
        } catch (error) {
            console.log('ℹ️ Status update failed:', error.message);
        }
    }

    async loadKeypoints() {
        try {
            const response = await fetch(`${this.apiBase}/api/keypoints/latest?limit=8`);
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            
            const keypoints = response.json();
            this.displayKeypoints(await keypoints);
            
        } catch (error) {
            console.error('❌ Failed to load keypoints:', error);
            this.showError('Failed to load keypoints: ' + error.message);
        }
    }

    displayKeypoints(keypoints) {
        const container = document.getElementById('latestKeypoints');
        
        if (!keypoints || keypoints.length === 0) {
            container.innerHTML = `
                <div class="loading">
                    <div>📭 No keypoints available</div>
                    <div style="font-size: 14px; color: #666; margin-top: 10px;">
                        Process some articles or start real-time processing to generate keypoints
                    </div>
                </div>
            `;
            return;
        }

        const keypointsHtml = keypoints.map((kp, index) => `
            <div class="keypoint-result" id="keypoint-${kp.id}">
                <div class="keypoint-text">
                    <strong>#${index + 1}</strong> ${kp.keypoint_text}
                </div>
                <div class="keypoint-meta">
                    <span>
                        🤖 ${kp.segment.model_used} | 
                        📅 ${new Date(kp.created_at).toLocaleTimeString()} |
                        🏷️ ${kp.segment.topic}
                    </span>
                    <span class="confidence-${this.getConfidenceClass(kp.confidence_score)}">
                        ${Math.round(kp.confidence_score * 100)}% confidence
                    </span>
                </div>
                <div class="keypoint-controls">
                    <button class="audio-btn" onclick="demo.playKeypointAudio('${kp.id}', this)">
                        🔊 Listen
                    </button>
                    <span class="tts-status" id="tts-status-${kp.id}"></span>
                </div>
                <div class="audio-player" id="audio-player-${kp.id}">
                    <audio controls id="audio-${kp.id}">
                        Your browser does not support the audio element.
                    </audio>
                </div>
            </div>
        `).join('');

        container.innerHTML = keypointsHtml;
    }

    startAutoRefresh() {
        // Refresh keypoints every 15 seconds
        setInterval(() => {
            if (!this.isProcessing) {
                this.loadKeypoints();
            }
        }, 15000);
    }

    async refreshNews() {
        this.showMessage('🔄 Refreshing news articles...', 'info');
        await this.loadNews();
        this.showMessage('✅ News articles refreshed', 'success');
    }

    async refreshKeypoints() {
        this.showMessage('🔄 Refreshing keypoints...', 'info');
        await this.loadKeypoints();
        this.showMessage('✅ Keypoints refreshed', 'success');
    }

    async compareModels() {
        const modelsInfo = this.models.map(model => `
            <tr>
                <td><strong>${model.name}</strong></td>
                <td>${model.description}</td>
                <td><span class="stat-badge speed-${model.speed}">${model.speed}</span></td>
                <td><span class="stat-badge accuracy-${model.accuracy.replace(' ', '-')}">${model.accuracy}</span></td>
                <td>${model.hf_model || 'N/A'}</td>
            </tr>
        `).join('');

        const comparisonHtml = `
            <table class="comparison-table">
                <thead>
                    <tr>
                        <th>Model Name</th>
                        <th>Description</th>
                        <th>Speed</th>
                        <th>Accuracy</th>
                        <th>HuggingFace Model</th>
                    </tr>
                </thead>
                <tbody>
                    ${modelsInfo}
                </tbody>
            </table>
        `;

        // Show in results section
        const container = document.getElementById('processingResults');
        const titleElement = document.getElementById('resultsTitle');
        const contentElement = document.getElementById('resultsContent');
        
        titleElement.textContent = 'STT Models Comparison';
        contentElement.innerHTML = comparisonHtml;
        container.style.display = 'block';
        
        container.scrollIntoView({ behavior: 'smooth' });
    }

    showMessage(message, type = 'info') {
        // Remove existing messages
        const existing = document.querySelector('.message');
        if (existing) existing.remove();
        
        // Create new message
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${type}`;
        messageDiv.textContent = message;
        
        // Insert after status section
        const statusSection = document.querySelector('.status-section');
        statusSection.insertAdjacentElement('afterend', messageDiv);
        
        // Auto-remove after 5 seconds
        setTimeout(() => {
            if (messageDiv.parentNode) {
                messageDiv.remove();
            }
        }, 5000);
    }

    showError(message) {
        this.showMessage('❌ ' + message, 'error');
    }

    // Text-to-Speech Methods
    async playKeypointAudio(keypointId, buttonElement) {
        try {
            const statusElement = document.getElementById(`tts-status-${keypointId}`);
            const audioPlayer = document.getElementById(`audio-player-${keypointId}`);
            const audioElement = document.getElementById(`audio-${keypointId}`);
            
            // Check if audio is already loaded
            if (audioElement.src && !audioElement.src.includes('blob:')) {
                // Audio already loaded, just play/pause
                if (audioElement.paused) {
                    audioElement.play();
                    buttonElement.textContent = '⏸️ Pause';
                    buttonElement.classList.add('playing');
                } else {
                    audioElement.pause();
                    buttonElement.textContent = '🔊 Listen';
                    buttonElement.classList.remove('playing');
                }
                return;
            }
            
            // Generate new audio
            buttonElement.disabled = true;
            buttonElement.textContent = '⏳ Generating...';
            statusElement.textContent = 'Generating audio...';
            
            const response = await fetch(`${this.apiBase}/api/tts/keypoint/${keypointId}`, {
                method: 'POST'
            });
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            // Get audio blob
            const audioBlob = await response.blob();
            const audioUrl = URL.createObjectURL(audioBlob);
            
            // Set up audio element
            audioElement.src = audioUrl;
            audioElement.onloadeddata = () => {
                statusElement.textContent = 'Audio ready';
                buttonElement.disabled = false;
                buttonElement.textContent = '▶️ Play';
                audioPlayer.style.display = 'block';
            };
            
            // Handle play/pause events
            audioElement.onplay = () => {
                buttonElement.textContent = '⏸️ Pause';
                buttonElement.classList.add('playing');
                statusElement.textContent = 'Playing...';
            };
            
            audioElement.onpause = () => {
                buttonElement.textContent = '▶️ Play';
                buttonElement.classList.remove('playing');
                statusElement.textContent = 'Paused';
            };
            
            audioElement.onended = () => {
                buttonElement.textContent = '🔊 Listen';
                buttonElement.classList.remove('playing');
                statusElement.textContent = 'Completed';
            };
            
            // Auto-play the generated audio
            setTimeout(() => {
                audioElement.play();
            }, 100);
            
        } catch (error) {
            console.error('❌ TTS Error:', error);
            
            const statusElement = document.getElementById(`tts-status-${keypointId}`);
            statusElement.textContent = 'Audio generation failed';
            statusElement.style.color = '#dc3545';
            
            buttonElement.disabled = false;
            buttonElement.textContent = '🔊 Listen';
            
            this.showError('Failed to generate audio: ' + error.message);
        }
    }

    async generateTextAudio(text) {
        """Generate audio for arbitrary text"""
        try {
            if (!text || text.trim().length === 0) {
                this.showError('Please provide text to convert to speech');
                return null;
            }
            
            if (text.length > 500) {
                this.showError('Text too long (max 500 characters)');
                return null;
            }
            
            const response = await fetch(`${this.apiBase}/api/tts/text`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ text: text.trim() })
            });
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            const audioBlob = await response.blob();
            return URL.createObjectURL(audioBlob);
            
        } catch (error) {
            console.error('❌ Text TTS Error:', error);
            this.showError('Failed to generate audio: ' + error.message);
            return null;
        }
    }

    async playResultKeypointAudio(text, index, buttonElement) {
        """Play audio for keypoints in processing results"""
        try {
            const statusElement = document.getElementById(`result-tts-status-${index}`);
            const audioPlayer = document.getElementById(`result-audio-player-${index}`);
            const audioElement = document.getElementById(`result-audio-${index}`);
            
            // Check if audio is already loaded
            if (audioElement.src && !audioElement.src.includes('blob:')) {
                // Audio already loaded, just play/pause
                if (audioElement.paused) {
                    audioElement.play();
                    buttonElement.textContent = '⏸️ Pause';
                    buttonElement.classList.add('playing');
                } else {
                    audioElement.pause();
                    buttonElement.textContent = '🔊 Listen';
                    buttonElement.classList.remove('playing');
                }
                return;
            }
            
            // Generate new audio
            buttonElement.disabled = true;
            buttonElement.textContent = '⏳ Generating...';
            statusElement.textContent = 'Generating audio...';
            
            const audioUrl = await this.generateTextAudio(text);
            
            if (!audioUrl) {
                throw new Error('Failed to generate audio');
            }
            
            // Set up audio element
            audioElement.src = audioUrl;
            audioElement.onloadeddata = () => {
                statusElement.textContent = 'Audio ready';
                buttonElement.disabled = false;
                buttonElement.textContent = '▶️ Play';
                audioPlayer.style.display = 'block';
            };
            
            // Handle play/pause events
            audioElement.onplay = () => {
                buttonElement.textContent = '⏸️ Pause';
                buttonElement.classList.add('playing');
                statusElement.textContent = 'Playing...';
            };
            
            audioElement.onpause = () => {
                buttonElement.textContent = '▶️ Play';
                buttonElement.classList.remove('playing');
                statusElement.textContent = 'Paused';
            };
            
            audioElement.onended = () => {
                buttonElement.textContent = '🔊 Listen';
                buttonElement.classList.remove('playing');
                statusElement.textContent = 'Completed';
            };
            
            // Auto-play the generated audio
            setTimeout(() => {
                audioElement.play();
            }, 100);
            
        } catch (error) {
            console.error('❌ Result TTS Error:', error);
            
            const statusElement = document.getElementById(`result-tts-status-${index}`);
            statusElement.textContent = 'Audio generation failed';
            statusElement.style.color = '#dc3545';
            
            buttonElement.disabled = false;
            buttonElement.textContent = '🔊 Listen';
            
            this.showError('Failed to generate audio: ' + error.message);
        }
    }
}

// Global functions
let demo;

async function startRealtime() {
    await demo.startRealtime();
}

async function stopRealtime() {
    await demo.stopRealtime();
}

async function refreshNews() {
    await demo.refreshNews();
}

async function refreshKeypoints() {
    await demo.refreshKeypoints();
}

async function compareModels() {
    await demo.compareModels();
}

// Initialize when page loads
document.addEventListener('DOMContentLoaded', () => {
    demo = new EnhancedNewsDemo();
});