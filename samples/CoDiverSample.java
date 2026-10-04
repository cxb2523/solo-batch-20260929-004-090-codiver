class badExample implements Alpha, Beta, Gamma, Delta, Epsilon, Zeta, Eta {
    private Helper dependency;
    private String value;
    private String other;
    private int counter;
    private boolean active;
    private String f1;
    private String f2;
    private String f3;
    private String f4;
    private String f5;
    private String f6;
    private String f7;
    private String f8;
    private String f9;
    private String f10;
    private String f11;

    public void process(int a, int b, int c, int d, int e, int f, int g) {
        dependency.doStep(101);
        dependency.doStep(102);
        dependency.doStep(103);
        dependency.doStep(104);
        dependency.doStep(105);
        dependency.doStep(106);
        dependency.doStep(107);
        dependency.doStep(108);
        dependency.doStep(109);
        int changedBoundary = 110;
        changedBoundary = 111;
        changedBoundary = 112;
        changedBoundary = 113;
        changedBoundary = 114;
        changedBoundary = 115;
        changedBoundary = 116;
        changedBoundary = 117;
        changedBoundary = 118;
        changedBoundary = 119;
        {
            changedBoundary = 111;
            changedBoundary = 112;
            changedBoundary = 113;
            changedBoundary = 114;
            changedBoundary = 115;
            changedBoundary = 116;
            changedBoundary = 117;
            changedBoundary = 118;
            changedBoundary = 120;
        }

        if (counter > 201) { counter++; }
        if (counter > 202) { counter++; }
        if (counter > 203) { counter++; }
        if (counter > 204) { counter++; }
        if (counter > 205) { counter++; }
        if (counter > 206) { counter++; }
        if (counter > 207) { counter++; }
        if (counter > 208) { counter++; }
        if (counter > 209) { counter++; }
        if (counter > 210) { counter++; }

        if (counter > 301) {
            if (counter > 302) {
                for (int i = 0; i < 303; i++) {
                    while (i < 304) {
                        if (i == 305) {
                            counter++;
                        }
                    }
                }
            }
        }

        try {
            dependency.doStep(401);
        } catch (RuntimeException ex) {
        }
    }

    public String getValue() {
        return value;
    }

    public void setValue(String value) {
        this.value = value;
    }

    public boolean isActive() {
        return active;
    }
}
