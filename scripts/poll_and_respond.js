const { WebClient } = require('@slack/web-api');
const axios = require('axios');

const slackToken = process.env.SLACK_BOT_TOKEN;
const openAiKey = process.env.OPENAI_API_KEY;
const slackClient = new WebClient(slackToken);

(async () => {
  try {
    // Fetch recent messages mentioning the bot
    const result = await slackClient.conversations.history({
      channel: 'YOUR_CHANNEL_ID', // Replace with the channel ID you want to poll
      limit: 10,
    });

    for (const message of result.messages) {
      if (message.text.includes('<@YOUR_BOT_USER_ID>')) { // Replace with your bot's user ID
        // Send message text to ChatGPT for a response
        const chatGptResponse = await axios.post(
          'https://api.openai.com/v1/completions',
          {
            model: 'text-davinci-003',
            prompt: message.text,
            max_tokens: 50,
          },
          {
            headers: { Authorization: `Bearer ${openAiKey}` },
          }
        );

        // Post ChatGPT's response back to Slack
        await slackClient.chat.postMessage({
          channel: message.channel,
          text: chatGptResponse.data.choices[0].text.trim(),
        });
      }
    }
  } catch (error) {
    console.error('Error running bot:', error);
  }
})();
