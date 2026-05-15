// Mystic Sanctuary — Shopping Cart
(function() {
    'use strict';

    function getCart() {
        try {
            return JSON.parse(localStorage.getItem('mystic_cart') || '[]');
        } catch(e) {
            return [];
        }
    }

    function saveCart(cart) {
        localStorage.setItem('mystic_cart', JSON.stringify(cart));
    }

    window.addToCart = function(product) {
        var cart = getCart();
        cart.push({
            sku: product.sku,
            title: product.title,
            price: parseFloat(product.price)
        });
        saveCart(cart);
        updateCartCount();
        showToast(product.title + ' added to cart!');
    };

    function updateCartCount() {
        var cart = getCart();
        var countEl = document.getElementById('cart-count');
        if (countEl) {
            countEl.textContent = cart.length;
            countEl.style.display = cart.length > 0 ? 'inline-block' : 'none';
        }
    }

    function showToast(message) {
        var existing = document.querySelector('.cart-toast');
        if (existing) existing.remove();

        var toast = document.createElement('div');
        toast.className = 'cart-toast';
        toast.textContent = message;
        toast.style.cssText = 'position:fixed;bottom:24px;right:24px;background:#6b4e7e;color:white;padding:12px 24px;border-radius:8px;z-index:9999;animation:slideUp 0.3s ease-out;font-size:14px;';
        document.body.appendChild(toast);

        var style = document.createElement('style');
        style.textContent = '@keyframes slideUp { from { transform: translateY(100px); opacity: 0; } to { transform: translateY(0); opacity: 1; } }';
        document.head.appendChild(style);

        setTimeout(function() {
            toast.style.opacity = '0';
            toast.style.transition = 'opacity 0.3s';
            setTimeout(function() { toast.remove(); }, 300);
        }, 2000);
    }

    // Attach event listeners to all "Add to Cart" buttons
    document.addEventListener('DOMContentLoaded', function() {
        updateCartCount();
        document.querySelectorAll('.add-to-cart').forEach(function(btn) {
            btn.addEventListener('click', function(e) {
                e.preventDefault();
                var sku = this.getAttribute('data-sku');
                var title = this.getAttribute('data-title');
                var price = this.getAttribute('data-price');
                addToCart({ sku: sku, title: title, price: price });
            });
        });
    });
})();
