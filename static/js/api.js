// ============================================
// API Configuration
// ============================================

// Your Render backend URL
const API_BASE_URL = 'https://olivintra-backend.onrender.com';

// ============================================
// Helper Functions
// ============================================

// Format price in Indian Rupees
function formatPrice(price) {
    return '₹' + parseFloat(price).toFixed(2);
}

// Create a product card HTML
function createProductCard(product) {
    const imageUrl = product.image 
        ? `static/uploads/${product.image}` 
        : 'static/images/placeholder.jpg';
    
    return `
        <div class="product-card" data-product-id="${product.id}">
            <a href="product.html?slug=${product.slug}">
                <img src="${imageUrl}" alt="${product.name}" loading="lazy">
                <h3>${product.name}</h3>
                <p class="price">${formatPrice(product.price)}</p>
                ${product.original_price ? `<p class="original-price">${formatPrice(product.original_price)}</p>` : ''}
                ${product.in_stock ? '<span class="in-stock">In Stock</span>' : '<span class="out-of-stock">Out of Stock</span>'}
            </a>
        </div>
    `;
}

// ============================================
// API Functions
// ============================================

// Fetch all products
async function getProducts() {
    try {
        const response = await fetch(`${API_BASE_URL}/api/products`);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        return await response.json();
    } catch (error) {
        console.error('Error fetching products:', error);
        return [];
    }
}

// Fetch a single product by slug
async function getProductBySlug(slug) {
    try {
        const response = await fetch(`${API_BASE_URL}/api/product/${slug}`);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        return await response.json();
    } catch (error) {
        console.error('Error fetching product:', error);
        return null;
    }
}

// Fetch categories
async function getCategories() {
    try {
        const response = await fetch(`${API_BASE_URL}/api/categories`);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        return await response.json();
    } catch (error) {
        console.error('Error fetching categories:', error);
        return [];
    }
}

// ============================================
// Display Functions
// ============================================

// Display products in a container
async function displayProducts(containerId, filter = null, limit = null) {
    const container = document.getElementById(containerId);
    if (!container) {
        console.warn(`Container with ID "${containerId}" not found`);
        return;
    }

    // Show loading state
    container.innerHTML = '<div class="loading">Loading products...</div>';

    const products = await getProducts();
    
    if (products.length === 0) {
        container.innerHTML = '<div class="no-products">No products available.</div>';
        return;
    }

    // Filter products if needed
    let filteredProducts = products;
    if (filter === 'new-arrivals') {
        filteredProducts = products.filter(p => p.is_new_arrival);
    } else if (filter === 'best-sellers') {
        filteredProducts = products.filter(p => p.is_best_seller);
    } else if (filter === 'featured') {
        filteredProducts = products.filter(p => p.is_featured);
    }

    // Limit the number of products
    if (limit && filteredProducts.length > limit) {
        filteredProducts = filteredProducts.slice(0, limit);
    }

    // Generate HTML for each product
    container.innerHTML = filteredProducts.map(product => createProductCard(product)).join('');
}

// ============================================
// Initialize when page loads
// ============================================

document.addEventListener('DOMContentLoaded', function() {
    // Display products in different sections
    displayProducts('new-arrivals-container', 'new-arrivals', 4);
    displayProducts('best-sellers-container', 'best-sellers', 4);
    displayProducts('featured-products-container', 'featured', 6);
    displayProducts('all-products-container', null, 12);
});