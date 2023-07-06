"""Define functional tests for the package."""
# def test_get_class_resources_endpoint():
#     """Test that the search endpoint works."""
#     class_ids: ClassResourceIds = [uuid4() for _ in range(5)]
#     request_mock = MagicMock()
#     try:
#         get_class_resources(class_ids, request_mock)
#     except ValidationError as e:
#         pytest.fail(f"Endpoint {get_class_resources} failed. Error: {str(e)}")