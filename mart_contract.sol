// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

contract SocialNetwork {
    struct Post {
        uint256 id;
        address author;
        string contentHash;
        uint256 timestamp;
    }
    
    mapping(uint256 => Post) public posts;
    uint256 public postCount;
    
    event PostCreated(uint256 indexed id, address indexed author, string contentHash, uint256 timestamp);
    
    function createPost(string memory contentHash) public {
        postCount++;
        posts[postCount] = Post(postCount, msg.sender, contentHash, block.timestamp);
        emit PostCreated(postCount, msg.sender, contentHash, block.timestamp);
    }
    
    function getPost(uint256 id) public view returns (Post memory) {
        return posts[id];
    }
}