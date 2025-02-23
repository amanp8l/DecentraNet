/ SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

contract PostStorage {
    struct Post {
        uint256 id;
        address author;
        string title;
        string content;
        string paperLink;
        uint256 timestamp;
    }
    
    Post[] public posts;
    mapping(uint256 => uint256) public postUpvotes;
    mapping(uint256 => string[]) public postComments;
    
    event PostCreated(uint256 indexed postId, address indexed author);
    
    function createPost(string memory title, string memory content, string memory paperLink) public returns (uint256) {
        uint256 postId = posts.length;
        posts.push(Post({
            id: postId,
            author: msg.sender,
            title: title,
            content: content,
            paperLink: paperLink,
            timestamp: block.timestamp
        }));
        
        emit PostCreated(postId, msg.sender);
        return postId;
    }
    
    function getPost(uint256 postId) public view returns (Post memory) {
        require(postId < posts.length, "Post does not exist");
        return posts[postId];
    }
    
    function getAllPosts() public view returns (Post[] memory) {
        return posts;
    }
    
    function addComment(uint256 postId, string memory comment) public {
        require(postId < posts.length, "Post does not exist");
        postComments[postId].push(comment);
    }
    
    function upvotePost(uint256 postId) public {
        require(postId < posts.length, "Post does not exist");
        postUpvotes[postId] += 1;
    }
}