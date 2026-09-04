#include <iostream>
#define GL_SILENCE_DEPRECATION //this is just to slinece the deprecation warnings on macOS, you can remove it if you are not on macOS
#include <GLFW/glfw3.h>
#include <vector>
#include <cmath>

//this is just a simple particle struct, you can expand it with more properties as needed
struct Particle {
    float x;
    float y;
    float z;

    float vx;
    float vy;
    float vz;

    float ay;
}; 

void drawParticle(const Particle& particle) {
    glPointSize(10.0f);

    glBegin(GL_POINTS);
// this is just for the color of the particle
    glColor3f(0.3f, 0.7f, 1.0f);

    glVertex3f(
        particle.x,
        particle.y,
        particle.z
    );
    glEnd();
}

int main(){
    if (glfwInit() == GLFW_FALSE) {
        std::cerr << "Failed to initialize GLFW" << std::endl;
        return -1;
    }

    GLFWwindow* window = glfwCreateWindow(800, 600, "Matter Bending", NULL, NULL);
    if (!window) {
        std::cerr << "Failed to create GLFW window" << std::endl;
        glfwTerminate();
        return -1;
    }

    glfwMakeContextCurrent(window);

    std::vector<Particle> particles; //this is to make about 100 particles

    for (int i = 0; i < 100; i++) {
        const int column = i % 10;
        const int row = i / 10;

        Particle p = {
        // position
            -0.81f + column * 0.18f + (row % 2) * 0.015f,
            -0.45f + row * 0.13f,
            0.0f,

        // velocity
            (((i * 37) % 17) - 8) * 0.008f,
            0.10f + ((i * 23) % 13) * 0.025f,
            0.0f,

        // acceleration
            -0.8f
    };

    particles.push_back(p);
    }

    //to makke the particle. aatually move we need delta tuime, so we will use glfwGetTime() to get the time since the program started
    float lastTime = glfwGetTime();
    const float FLOOR_Y = -0.8f; //for the floor position

    while (!glfwWindowShouldClose(window)) {

        float currentTime = glfwGetTime();
        float dt = currentTime - lastTime;
        lastTime = currentTime;
        //this update the particle postion every frame based on its velocity and the time elapsed since the last frame

        glClear(GL_COLOR_BUFFER_BIT);

        for (auto& particle : particles) {
            particle.vy += particle.ay * dt;    

            particle.x += particle.vx * dt;
            particle.y += particle.vy * dt;
            particle.z += particle.vz * dt;

            //this is to check collision with floor
            if (particle.y <= FLOOR_Y) {
                particle.y = FLOOR_Y;
                particle.vy = -particle.vy * 0.75f;
            }

            drawParticle(particle);
        }

        glfwSwapBuffers(window);
        glfwPollEvents();

    }
}
