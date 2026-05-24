"""
Auto-generated interface layer code from InterfacePlan.
This layer is the ONLY layer allowed to directly access global variables.
"""

import datetime


# === Resource: books ===

def get_book(book_id: int) -> dict | None:
    return books.get(book_id)

def list_books(status_filter: str = 'all') -> list:
    if status_filter == 'all':
        return list(books.values())
    return [book for book in books.values() if book.get('status') == status_filter]

def create_book(book_id: int, title: str, author: str, status: str = 'available') -> dict:
    book = {'book_id': book_id, 'title': title, 'author': author, 'status': status}
    books[book_id] = book
    return book

def update_book(book_id: int, title: str = None, author: str = None, status: str = None) -> dict:
    book = books[book_id]
    if title is not None:
        book['title'] = title
    if author is not None:
        book['author'] = author
    if status is not None:
        book['status'] = status
    return book

def delete_book(book_id: int) -> None:
    del books[book_id]

def book_exists(book_id: int) -> bool:
    return book_id in books

# === Resource: next_id ===

def get_next_id() -> int:
    return next_id

def increment_next_id() -> int:
    global next_id
    next_id += 1
    return next_id