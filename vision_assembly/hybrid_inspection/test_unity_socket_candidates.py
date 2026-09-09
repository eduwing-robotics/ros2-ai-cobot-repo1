from extract_unity_socket_candidates import extract


def test_horizontal_dimension_match_and_negative_indices(tmp_path):
    mesh = tmp_path/'test.obj'
    mesh.write_text('v 0 0 0\nv 1 0 0\nv 1 0 2\nv 0 0 2\nf -4 -3 -2 -1\n')
    rows = extract(mesh, {'component_types': {'test': {'socket_size_local_mm': [20,10]}}})
    assert len(rows) == 1
    assert rows[0]['center_obj_xz_mm'] == [5,10]
    assert rows[0]['polygon_obj_xz_mm'] == [[0,0],[10,0],[10,20],[0,20]]


def test_sloped_face_not_socket_floor(tmp_path):
    mesh = tmp_path/'test.obj'
    mesh.write_text('v 0 0 0\nv 1 0 0\nv 1 1 2\nv 0 0 2\nf 1 2 3 4\n')
    assert extract(mesh, {'component_types': {'test': {'socket_size_local_mm': [10,20]}}}) == []
