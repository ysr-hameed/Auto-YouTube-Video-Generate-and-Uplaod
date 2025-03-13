
document.addEventListener('DOMContentLoaded', function() {
    // Elements
    const generateQuoteBtn = document.getElementById('generateQuoteBtn');
    const createVideoBtn = document.getElementById('createVideoBtn');
    const uploadYoutubeBtn = document.getElementById('uploadYoutubeBtn');
    const quoteLine1 = document.getElementById('quoteLine1');
    const quoteLine2 = document.getElementById('quoteLine2');
    const quoteAuthor = document.getElementById('quoteAuthor');
    const musicSelector = document.getElementById('musicSelector');
    const songDetails = document.getElementById('songDetails');
    const statusMessage = document.getElementById('statusMessage');
    const progressFill = document.getElementById('progressFill');
    
    let currentQuote = '';
    let currentAuthor = '';
    let selectedSong = null;
    let videoPath = null;
    
    // Check if auto-start is enabled
    const autoStart = document.body.getAttribute('data-auto-start') === 'true';
    
    // Load trending songs
    fetchTrendingSongs();
    
    // Auto-start process if enabled
    if (autoStart) {
        statusMessage.textContent = 'Auto-starting the process...';
        setTimeout(() => {
            generateQuote();
        }, 2000);
    }
    
    // Event listeners
    if (generateQuoteBtn) {
        generateQuoteBtn.addEventListener('click', generateQuote);
    }
    
    if (createVideoBtn) {
        createVideoBtn.addEventListener('click', createVideo);
    }
    
    if (uploadYoutubeBtn) {
        uploadYoutubeBtn.addEventListener('click', uploadToYoutube);
    }
    
    if (musicSelector) {
        musicSelector.addEventListener('change', function() {
            const songId = this.value;
            if (songId && window.trendingSongs) {
                selectedSong = window.trendingSongs.find(song => song.url === songId);
                songDetails.textContent = `Selected: ${selectedSong.title} by ${selectedSong.artist}`;
            } else {
                songDetails.textContent = '';
            }
        });
    }
    
    // Functions
    function fetchTrendingSongs() {
        fetch('/get_trending_audio')
            .then(response => response.json())
            .then(data => {
                if (data.songs && data.songs.length > 0) {
                    window.trendingSongs = data.songs;
                    
                    // Clear and populate the music selector
                    musicSelector.innerHTML = '';
                    musicSelector.disabled = false;
                    
                    const defaultOption = document.createElement('option');
                    defaultOption.value = '';
                    defaultOption.textContent = 'Select a song';
                    musicSelector.appendChild(defaultOption);
                    
                    data.songs.forEach(song => {
                        const option = document.createElement('option');
                        option.value = song.url;
                        option.textContent = `${song.title} - ${song.artist}`;
                        musicSelector.appendChild(option);
                    });
                }
            })
            .catch(error => {
                console.error('Error fetching songs:', error);
                statusMessage.textContent = 'Failed to load trending songs';
            });
    }
    
    function generateQuote() {
        statusMessage.textContent = 'Generating quote...';
        progressFill.style.width = '30%';
        
        // Reset the quote display
        quoteLine1.textContent = '';
        quoteLine2.textContent = '';
        quoteAuthor.textContent = '';
        quoteLine1.classList.remove('visible');
        quoteLine2.classList.remove('visible');
        quoteAuthor.classList.remove('visible');
        
        fetch('/generate_quote', {
            method: 'POST',
        })
            .then(response => response.json())
            .then(data => {
                if (data.error) {
                    throw new Error(data.error);
                }
                
                currentQuote = data.quote;
                currentAuthor = data.author;
                
                // Split the quote into two lines if needed
                const lines = currentQuote.split('. ');
                
                if (lines.length >= 2) {
                    quoteLine1.textContent = lines[0] + '.';
                    quoteLine2.textContent = lines.slice(1).join('. ');
                } else {
                    quoteLine1.textContent = currentQuote;
                    quoteLine2.textContent = '';
                }
                
                quoteAuthor.textContent = '- ' + currentAuthor;
                
                // Animate the quote appearance
                setTimeout(() => {
                    quoteLine1.classList.add('visible');
                    
                    setTimeout(() => {
                        if (quoteLine2.textContent) {
                            quoteLine2.classList.add('visible');
                        }
                        
                        setTimeout(() => {
                            quoteAuthor.classList.add('visible');
                            createVideoBtn.disabled = false;
                            statusMessage.textContent = 'Quote generated! You can now create a video.';
                            progressFill.style.width = '100%';
                            
                            setTimeout(() => {
                                progressFill.style.width = '0%';
                                
                                // Auto-start video creation if trending songs are loaded
                                if (document.body.getAttribute('data-auto-start') === 'true' && window.trendingSongs && window.trendingSongs.length > 0) {
                                    // Auto-select the first song
                                    if (musicSelector.options.length > 1) {
                                        musicSelector.selectedIndex = 1; // Select first real song, not the placeholder
                                        const songId = musicSelector.value;
                                        selectedSong = window.trendingSongs.find(song => song.url === songId);
                                        songDetails.textContent = `Selected: ${selectedSong.title} by ${selectedSong.artist}`;
                                        
                                        // Create the video automatically
                                        setTimeout(() => {
                                            createVideo();
                                        }, 1000);
                                    }
                                }
                            }, 1000);
                        }, 500);
                    }, 3000); // Second line appears after 3 seconds
                }, 500);
            })
            .catch(error => {
                console.error('Error generating quote:', error);
                statusMessage.textContent = 'Failed to generate quote: ' + error.message;
                progressFill.style.width = '0%';
            });
    }
    
    function createVideo() {
        if (!currentQuote) {
            statusMessage.textContent = 'Please generate a quote first';
            return;
        }
        
        statusMessage.textContent = 'Creating video with trending audio...';
        progressFill.style.width = '50%';
        
        // Use first available song or proceed without music if none is available
        let audioUrl = '';
        if (window.trendingSongs && window.trendingSongs.length > 0) {
            audioUrl = window.trendingSongs[0].url;
        }
        
        fetch('/create_video', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                quote: currentQuote,
                author: currentAuthor,
                audio_url: audioUrl
            })
        })
            .then(response => response.json())
            .then(data => {
                if (data.error) {
                    throw new Error(data.error);
                }
                
                videoPath = data.video_path;
                uploadYoutubeBtn.disabled = false;
                statusMessage.textContent = 'Video created successfully! You can now upload to YouTube.';
                progressFill.style.width = '100%';
                
                setTimeout(() => {
                    progressFill.style.width = '0%';
                    
                    // Auto-upload if auto-start is enabled
                    if (document.body.getAttribute('data-auto-start') === 'true') {
                        setTimeout(() => {
                            uploadToYoutube();
                        }, 1000);
                    }
                }, 1000);
            })
            .catch(error => {
                console.error('Error creating video:', error);
                statusMessage.textContent = 'Failed to create video: ' + error.message;
                progressFill.style.width = '0%';
            });
    }
    
    function uploadToYoutube() {
        if (!videoPath) {
            statusMessage.textContent = 'Please create a video first';
            return;
        }
        
        statusMessage.textContent = 'Uploading to YouTube...';
        progressFill.style.width = '70%';
        
        fetch('/upload_to_youtube', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                video_path: videoPath,
                quote: currentQuote,
                author: currentAuthor
            })
        })
            .then(response => response.json())
            .then(data => {
                if (data.error) {
                    throw new Error(data.error);
                }
                
                statusMessage.textContent = 'Video uploaded to YouTube successfully! ' + data.message;
                progressFill.style.width = '100%';
                
                setTimeout(() => {
                    progressFill.style.width = '0%';
                }, 2000);
            })
            .catch(error => {
                console.error('Error uploading to YouTube:', error);
                
                if (error.message.includes('Not authenticated')) {
                    statusMessage.textContent = 'Please authenticate with YouTube first';
                } else {
                    statusMessage.textContent = 'Failed to upload to YouTube: ' + error.message;
                }
                
                progressFill.style.width = '0%';
            });
    }
});
