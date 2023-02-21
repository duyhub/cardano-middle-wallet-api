# Cardano trading API for NFT trading

This repo is part of my project when making a NFT trading service on Cardano blockchain. It uses Cardano CLI to make middle wallet and allow trading between NFT buyer and seller.

**Note**: This method was prior to smart contract release on Cardano. 

---

## How it works
Each time the trade occurs, the buyers will deposit their ADA into a new middle wallet created by the service. Then, the sellers sent their NFTs to that same wallet. 

When the middle wallet's received the funds and items, NFTs and ADA will be sent back to its new owners and a small fraction of ADAs will be sent to the service provider's wallet as a fee.