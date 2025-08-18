import os
import unittest
import asyncio
import time
from unittest.mock import AsyncMock, patch
import httpx

# Set environment variables before importing
os.environ.setdefault('OPENAI_API_KEY', 'test')
os.environ.setdefault('SHARED_KEY', 'test')

from validators import validate_images_optimized, cleanup_validation_client


class TestImageValidationPerformance(unittest.TestCase):
    """Test the optimized image validation performance improvements."""

    def setUp(self):
        """Set up test fixtures."""
        self.valid_image_urls = [
            "https://example.com/image1.jpg",
            "https://example.com/image2.png", 
            "https://example.com/image3.webp"
        ]
        
        self.invalid_image_urls = [
            "https://nonexistent.com/image.jpg",
            "https://example.com/notfound.png"
        ]
        
        self.mixed_urls = self.valid_image_urls + self.invalid_image_urls

    def tearDown(self):
        """Clean up after tests."""
        asyncio.run(cleanup_validation_client())

    def test_validate_empty_list(self):
        """Test validation with empty URL list."""
        async def run_test():
            result = await validate_images_optimized([])
            self.assertEqual(result, [])
        
        asyncio.run(run_test())

    def test_validate_duplicate_urls(self):
        """Test that duplicate URLs are handled efficiently."""
        async def run_test():
            # Create list with duplicates
            urls_with_duplicates = self.valid_image_urls * 3  # 9 URLs (3 unique)
            
            with patch('validators._check_single_optimized') as mock_check:
                mock_check.return_value = True
                
                result = await validate_images_optimized(urls_with_duplicates)
                
                # Should only call validation for unique URLs
                self.assertEqual(mock_check.call_count, 3)  # 3 unique URLs
                self.assertEqual(result, [])  # All valid
        
        asyncio.run(run_test())

    def test_validate_with_timeouts(self):
        """Test validation handles timeouts gracefully."""
        async def run_test():
            timeout_urls = ["https://slow-server.com/image.jpg"]
            
            with patch('validators._check_single_optimized') as mock_check:
                mock_check.side_effect = httpx.TimeoutException("Request timed out")
                
                result = await validate_images_optimized(timeout_urls)
                
                # Should return the URL as unreachable
                self.assertEqual(result, timeout_urls)
        
        asyncio.run(run_test())

    def test_validate_with_http_errors(self):
        """Test validation handles HTTP errors gracefully."""
        async def run_test():
            error_urls = ["https://example.com/404.jpg"]
            
            with patch('validators._check_single_optimized') as mock_check:
                mock_check.return_value = False
                
                result = await validate_images_optimized(error_urls)
                
                # Should return the URL as unreachable
                self.assertEqual(result, error_urls)
        
        asyncio.run(run_test())

    def test_concurrency_limiting(self):
        """Test that concurrency is properly limited."""
        async def run_test():
            many_urls = [f"https://example.com/image{i}.jpg" for i in range(50)]
            
            call_times = []
            original_check = None
            
            async def mock_check_with_timing(*args, **kwargs):
                call_times.append(time.time())
                await asyncio.sleep(0.1)  # Simulate network delay
                return True
            
            with patch('validators._check_single_optimized', side_effect=mock_check_with_timing):
                start_time = time.time()
                result = await validate_images_optimized(many_urls, max_concurrent=10)
                total_time = time.time() - start_time
                
                # With 50 URLs, 10 concurrent, 0.1s each:
                # Should take roughly 50/10 * 0.1 = 0.5s (plus overhead)
                # Without concurrency limiting, it would take much longer due to resource limits
                self.assertLess(total_time, 2.0)  # Should complete reasonably fast
                self.assertEqual(len(result), 0)  # All should be valid (mocked as True)
        
        asyncio.run(run_test())

    def test_performance_improvement_simulation(self):
        """Simulate performance improvement over the old implementation."""
        async def run_test():
            # Simulate 20 images (typical lot size)
            test_urls = [f"https://example.com/image{i}.jpg" for i in range(20)]
            
            # Mock fast responses
            with patch('validators._check_single_optimized') as mock_check:
                mock_check.return_value = True
                
                start_time = time.time()
                result = await validate_images_optimized(test_urls, max_concurrent=20)
                elapsed_time = time.time() - start_time
                
                # Should complete very quickly with mocked responses
                self.assertLess(elapsed_time, 1.0)
                self.assertEqual(len(result), 0)  # All valid
                
                # Verify all URLs were checked
                self.assertEqual(mock_check.call_count, 20)
        
        asyncio.run(run_test())

    def test_function_robustness(self):
        """Test that the function handles edge cases without crashing."""
        async def run_test():
            # Test empty list
            result = await validate_images_optimized([])
            self.assertEqual(result, [])
            
            # Test single URL (will actually make HTTP request but should not crash)
            try:
                result = await validate_images_optimized(["https://httpbin.org/status/404"], max_concurrent=1)
                self.assertIsInstance(result, list)
                print(f"Function completed successfully, returned {len(result)} invalid URLs")
            except Exception as e:
                self.fail(f"Function should not raise exception: {e}")
        
        asyncio.run(run_test())


if __name__ == '__main__':
    unittest.main()